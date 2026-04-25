"""
LangGraph coordinator-worker graph for EWA analysis.

Topology:
    START → planner → [Send(domain_analyst) × N in parallel]
          → cross_reference → synthesize → END

planner       (gpt-5.4)       Reads the tree, produces a prioritised SectionTask list.
domain_analyst (gpt-5.4-mini) Runs in parallel — one invocation per section.
cross_reference (gpt-5.4)     Correlates findings across all sections.
synthesize     (gpt-5.4)      Writes executive summary + overall health + top-5 actions.
"""

from __future__ import annotations

import json
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from ewa_pipeline.config import Config
from ewa_pipeline.models import get_orchestrator_model, get_subagent_model, get_cross_ref_model
from ewa_pipeline.tracking.cost_tracker import CostTracker
from ewa_pipeline.report.schemas import (
    DomainAnalysis, CrossReferenceList, OrchestratorPlan, SynthesisResult,
)
from .prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    ORCHESTRATOR_PLANNING_PROMPT,
    DOMAIN_ANALYST_PROMPT,
    CROSS_REFERENCE_PROMPT,
)


# ── State ─────────────────────────────────────────────────────────────────────

class EwaAnalysisState(TypedDict):
    # Inputs — set once before the graph runs
    tree_summary: str
    sections_available: list[dict]       # [{id, title, summary}] — for planner
    sections_content: dict[str, str]     # section_id → markdown content
    skills_content: str

    # After planner node
    section_tasks: list[dict]            # [{section_id, section_title, analysis_focus}]
    planning_notes: str

    # Accumulated from parallel domain_analyst nodes
    domain_analyses: Annotated[list[DomainAnalysis], operator.add]
    failed_sections: Annotated[list[str], operator.add]

    # After cross_reference node
    cross_references: list

    # After synthesize node
    executive_summary: str
    overall_system_health: str
    top_5_priority_actions: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tokens(raw: Any) -> tuple[int, int]:
    meta = getattr(raw, "usage_metadata", None) or {}
    return meta.get("input_tokens", 0), meta.get("output_tokens", 0)


def _derive_health(analyses: list[DomainAnalysis]) -> str:
    healths = {da.overall_health for da in analyses}
    if "Critical" in healths:
        return "Critical"
    if "Warning" in healths:
        return "Warning"
    return "Healthy"


# ── Graph factory ─────────────────────────────────────────────────────────────

def build_ewa_graph(config: Config, cost_tracker: CostTracker):
    """
    Compile and return the LangGraph EWA analysis graph.

    Nodes are closures — they capture config, cost_tracker, and LLM chains.
    Call graph.stream(initial_state) to run with streaming event output.
    """
    medium_deployment = config.azure_openai.deployments.medium
    big_deployment = config.azure_openai.deployments.big

    planner_chain = get_orchestrator_model(config).with_structured_output(
        OrchestratorPlan, include_raw=True
    )
    domain_chain = get_subagent_model(config).with_structured_output(
        DomainAnalysis, include_raw=True
    )
    xref_chain = get_cross_ref_model(config).with_structured_output(
        CrossReferenceList, include_raw=True
    )
    synth_chain = get_orchestrator_model(config).with_structured_output(
        SynthesisResult, include_raw=True
    )

    # ── Node: planner ────────────────────────────────────────────────────────

    def planner(state: EwaAnalysisState) -> dict:
        """
        Orchestrator LLM reads the tree and produces a prioritised SectionTask list.
        Each task carries an analysis_focus hint that guides the domain analyst.
        """
        sections_text = "\n".join(
            f"  id={s['id']} | {s['title']}: {s.get('summary', '')[:120]}"
            for s in state["sections_available"]
        )
        prompt = ORCHESTRATOR_PLANNING_PROMPT.format(
            tree_summary=state["tree_summary"],
            sections=sections_text,
            skills_excerpt=state["skills_content"][:2000],
        )
        result = planner_chain.invoke(
            [SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        inp, out = _tokens(result.get("raw"))
        cost_tracker.record("phase0_planning", big_deployment, inp, out)

        plan: OrchestratorPlan = result["parsed"]
        return {
            "section_tasks": [t.model_dump() for t in plan.tasks],
            "planning_notes": plan.planning_notes,
        }

    # ── Conditional edge: fan out sections to parallel domain analysts ────────

    def route_sections(state: EwaAnalysisState) -> list[Send] | str:
        """
        Dispatch each section task as a parallel Send to domain_analyst.
        Falls through to cross_reference directly if the planner produced no tasks.
        """
        if not state["section_tasks"]:
            return "cross_reference"

        # Build a title lookup so we trust the tree index, not the planner's echo
        title_lookup = {s["id"]: s["title"] for s in state["sections_available"]}

        sends = []
        for task in state["section_tasks"]:
            # Normalise the id the planner returned: strip any bracket/quote wrapping
            # (e.g. "[0031]" → "0031") before looking up content.
            raw_id = task["section_id"]
            sid = raw_id.strip("[]'\"") if isinstance(raw_id, str) else str(raw_id)
            sends.append(Send("domain_analyst", {
                "section_id": sid,
                "section_title": title_lookup.get(sid, task.get("section_title", sid)),
                "content": state["sections_content"].get(sid, ""),
                "skills_content": state["skills_content"],
                "analysis_focus": task.get("analysis_focus", ""),
            }))
        return sends

    # ── Node: domain_analyst ─────────────────────────────────────────────────

    def domain_analyst(task: dict) -> dict:
        """
        Analyse a single section. Runs in parallel — one invocation per Send.
        Returns {"domain_analyses": [da]} which is accumulated via operator.add.
        """
        prompt = DOMAIN_ANALYST_PROMPT.format(
            section_title=task["section_title"],
            section_id=task["section_id"],
            content=task["content"],
            skills_excerpt=task["skills_content"][:3000],
            analysis_focus=task["analysis_focus"],
        )
        try:
            result = domain_chain.invoke([HumanMessage(content=prompt)])
            inp, out = _tokens(result.get("raw"))
            cost_tracker.record("phase1_domain_analysis", medium_deployment, inp, out)
            da: DomainAnalysis = result["parsed"]
            return {"domain_analyses": [da]}
        except Exception as exc:
            return {
                "domain_analyses": [],
                "failed_sections": [
                    f"{task['section_id']} ({task['section_title']}): {exc}"
                ],
            }

    # ── Node: cross_reference ────────────────────────────────────────────────

    def cross_reference(state: EwaAnalysisState) -> dict:
        all_findings = {
            da.section_id: da.model_dump()
            for da in state["domain_analyses"]
        }
        prompt = CROSS_REFERENCE_PROMPT.format(
            all_findings=json.dumps(all_findings, indent=2)
        )
        try:
            result = xref_chain.invoke([HumanMessage(content=prompt)])
            inp, out = _tokens(result.get("raw"))
            cost_tracker.record("phase2_cross_reference", big_deployment, inp, out)
            xref_list: CrossReferenceList = result["parsed"]
            return {"cross_references": xref_list.items}
        except Exception:
            return {"cross_references": []}

    # ── Node: synthesize ─────────────────────────────────────────────────────

    def synthesize(state: EwaAnalysisState) -> dict:
        all_findings_text = json.dumps(
            [da.model_dump() for da in state["domain_analyses"]], indent=2
        )
        cross_refs_text = json.dumps(
            [xr.model_dump() if hasattr(xr, "model_dump") else xr
             for xr in state["cross_references"]],
            indent=2,
        )
        prompt = f"""You have completed analysis of all sections in an SAP EWA report.

Tree structure:
{state['tree_summary'][:3000]}

All domain findings:
{all_findings_text}

Cross-domain correlations:
{cross_refs_text}

Write the final synthesis:
- overall_system_health: Critical if ANY domain is Critical; Warning if ANY domain is Warning; else Healthy
- top_5_priority_actions: ordered by urgency x impact, referencing specific findings and SAP transactions
- executive_summary: 3-5 paragraphs covering system overview, critical/high findings, key risks, priorities
  Use specific numbers, finding IDs, and SAP transactions — no vague language.
"""
        try:
            result = synth_chain.invoke(
                [SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT), HumanMessage(content=prompt)]
            )
            inp, out = _tokens(result.get("raw"))
            cost_tracker.record("phase2_synthesis", big_deployment, inp, out)
            synthesis: SynthesisResult = result["parsed"]
            return {
                "executive_summary": synthesis.executive_summary,
                "overall_system_health": synthesis.overall_system_health,
                "top_5_priority_actions": synthesis.top_5_priority_actions,
            }
        except Exception:
            return {
                "executive_summary": "Synthesis unavailable.",
                "overall_system_health": _derive_health(state["domain_analyses"]),
                "top_5_priority_actions": [],
            }

    # ── Compile ───────────────────────────────────────────────────────────────

    builder = StateGraph(EwaAnalysisState)
    builder.add_node("planner", planner)
    builder.add_node("domain_analyst", domain_analyst)
    builder.add_node("cross_reference", cross_reference)
    builder.add_node("synthesize", synthesize)

    builder.add_edge(START, "planner")
    builder.add_conditional_edges(
        "planner", route_sections, ["domain_analyst", "cross_reference"]
    )
    builder.add_edge("domain_analyst", "cross_reference")
    builder.add_edge("cross_reference", "synthesize")
    builder.add_edge("synthesize", END)

    return builder.compile()
