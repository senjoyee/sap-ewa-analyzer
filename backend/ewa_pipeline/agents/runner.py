from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ewa_pipeline.config import Config
from ewa_pipeline.indexer.tree_navigator import TreeNode, get_node_content, tree_to_summary
from ewa_pipeline.tracking.cost_tracker import CostTracker
from ewa_pipeline.tracking.token_tracker import TokenUsage
from ewa_pipeline.report.schemas import AnalysisResult, DomainAnalysis
from ewa_pipeline.services.progress import ProgressCallback, ProgressReporter
from .orchestrator import EwaAnalysisState, build_ewa_graph

console = Console()


def _load_skills(skills_dir: Path) -> str:
    """Read skills/ewa-analysis/SKILL.md and any reference files into one string."""
    if not skills_dir.exists():
        return ""
    parts: list[str] = []
    skill_md = skills_dir / "ewa-analysis" / "SKILL.md"
    if skill_md.exists():
        parts.append(skill_md.read_text(encoding="utf-8"))
    refs_dir = skills_dir / "ewa-analysis" / "references"
    if refs_dir.exists():
        for ref in sorted(refs_dir.glob("*.md")):
            parts.append(ref.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


# Annotated[list, operator.add] fields — merged by appending, not overwriting
_ACCUMULATOR_KEYS = frozenset({"domain_analyses", "failed_sections"})


def run_analysis(
    config: Config,
    tree: dict,
    pages: dict[int, str],
    sections: list[TreeNode],
    skills_dir: Path,
    cost_tracker: CostTracker,
    verbose: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> AnalysisResult:
    """
    Run the full LangGraph EWA analysis pipeline.

    Graph topology:
        planner → [domain_analyst × N in parallel] → cross_reference → synthesize

    State is accumulated during a single graph.stream() pass — no double invocation.
    """
    reporter = ProgressReporter(progress_callback)

    # ── Build initial state ───────────────────────────────────────────────────

    skills_content = _load_skills(skills_dir)
    sections_available = [
        {"id": node.id, "title": node.title, "summary": node.summary}
        for node in sections
    ]
    sections_content = {
        node.id: get_node_content(pages, node)
        for node in sections
    }

    initial_state: EwaAnalysisState = {
        "tree_summary": tree_to_summary(tree),
        "sections_available": sections_available,
        "sections_content": sections_content,
        "skills_content": skills_content,
        "section_tasks": [],
        "planning_notes": "",
        "domain_analyses": [],
        "failed_sections": [],
        "cross_references": [],
        "executive_summary": "",
        "overall_system_health": "Healthy",
        "top_5_priority_actions": [],
    }

    if verbose:
        console.print(f"  Tree summary:\n{initial_state['tree_summary'][:800]}")
        console.print(f"  Skills loaded: {len(skills_content)} chars")

    # ── Stream graph, report progress, accumulate final state ─────────────────

    graph = build_ewa_graph(config, cost_tracker)
    total_sections = len(sections)
    analyzed_count = 0

    # We accumulate state deltas ourselves so we don't need a second invoke() call.
    # Annotated[list, operator.add] fields are appended; all others are overwritten.
    accumulated: dict = dict(initial_state)

    reporter.emit(
        "planning",
        "running",
        "Orchestrator planning analysis",
        detail=f"{total_sections} sections available",
    )

    for chunk in graph.stream(initial_state, stream_mode="updates"):
        for node_name, update in chunk.items():

            # ── Accumulate state ─────────────────────────────────────────────
            for key, value in update.items():
                if key in _ACCUMULATOR_KEYS:
                    accumulated[key] = accumulated.get(key, []) + (
                        value if isinstance(value, list) else []
                    )
                else:
                    accumulated[key] = value

            # ── Progress events ──────────────────────────────────────────────
            if node_name == "planner":
                num_tasks = len(update.get("section_tasks", []))
                notes = update.get("planning_notes", "")
                reporter.emit(
                    "planning",
                    "completed",
                    "Analysis plan ready",
                    detail=f"{num_tasks} sections selected"
                    + (f" — {notes}" if notes else ""),
                )
                reporter.emit(
                    "analyzing_sections",
                    "running",
                    "Analyzing sections",
                    detail=f"0 / {num_tasks}",
                    current=0,
                    total=num_tasks or 1,
                )
                if verbose:
                    console.print(
                        f"  [cyan]Plan[/cyan]: {num_tasks} sections"
                        + (f" — {notes}" if notes else "")
                    )

            elif node_name == "domain_analyst":
                new_das: list[DomainAnalysis] = update.get("domain_analyses", [])
                new_failures: list[str] = update.get("failed_sections", [])
                analyzed_count += len(new_das) + len(new_failures)
                planned = len(accumulated.get("section_tasks", [])) or total_sections

                for da in new_das:
                    if verbose:
                        color = {"Critical": "red", "Warning": "yellow", "Healthy": "green"}.get(
                            da.overall_health, "white"
                        )
                        console.print(
                            f"  [{color}]{da.overall_health}[/{color}]"
                            f" {da.section_title} — {len(da.findings)} finding(s)"
                        )
                for fail in new_failures:
                    console.print(f"  [yellow]Warning[/yellow]: {fail}")

                reporter.emit(
                    "analyzing_sections",
                    "running",
                    "Analyzing sections",
                    detail=f"{analyzed_count} / {planned}",
                    current=analyzed_count,
                    total=planned,
                )

            elif node_name == "cross_reference":
                xrefs = update.get("cross_references", [])
                reporter.emit(
                    "analyzing_sections",
                    "completed",
                    "Section analysis complete",
                    detail=f"{analyzed_count} sections processed",
                    current=analyzed_count,
                    total=analyzed_count or 1,
                )
                reporter.emit(
                    "correlating_findings",
                    "completed",
                    "Cross-referencing complete",
                    detail=f"{len(xrefs)} correlations",
                )

            elif node_name == "synthesize":
                reporter.emit(
                    "synthesizing",
                    "completed",
                    "Synthesis complete",
                    detail=update.get("overall_system_health", ""),
                )

    # ── Build AnalysisResult from accumulated state ───────────────────────────

    domain_analyses: list[DomainAnalysis] = accumulated["domain_analyses"]
    cross_references = accumulated["cross_references"]

    p1 = cost_tracker._entries.get("phase1_domain_analysis")
    p2a = cost_tracker._entries.get("phase2_cross_reference")
    p2b = cost_tracker._entries.get("phase2_synthesis")
    token_usage = TokenUsage(
        phase1_input_tokens=(p1.input_tokens if p1 else 0),
        phase1_output_tokens=(p1.output_tokens if p1 else 0),
        phase2_input_tokens=(
            (p2a.input_tokens if p2a else 0) + (p2b.input_tokens if p2b else 0)
        ),
        phase2_output_tokens=(
            (p2a.output_tokens if p2a else 0) + (p2b.output_tokens if p2b else 0)
        ),
    )

    return AnalysisResult(
        domain_analyses=domain_analyses,
        cross_references=cross_references,
        executive_summary=accumulated["executive_summary"],
        overall_system_health=accumulated["overall_system_health"],
        top_5_priority_actions=accumulated["top_5_priority_actions"],
        token_usage=token_usage,
    )
