from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ewa_pipeline.agents.runner import run_analysis
from ewa_pipeline.config import Config
from ewa_pipeline.indexer.tree_navigator import get_analyzable_sections
from ewa_pipeline.report import excel_generator
from ewa_pipeline.report.schemas import AnalysisResult
from ewa_pipeline.tracking.cost_tracker import CostTracker
from .progress import ProgressCallback, ProgressReporter

console = Console()


@dataclass(slots=True)
class PipelineArtifacts:
    output_path: Path
    result_path: Path
    cost_path: Path
    tree_path: Path
    doc_name: str


def run_pipeline(
    *,
    config: Config,
    output_path: Path,
    pdf_path: Path | None = None,
    zip_path: Path | None = None,
    input_path: Path | None = None,
    skip_index: bool = False,
    skip_analysis: bool = False,
    verbose: bool = False,
    skills_dir: Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[AnalysisResult, CostTracker, PipelineArtifacts]:
    provided = sum(x is not None for x in (pdf_path, zip_path, input_path))
    if provided == 0:
        raise ValueError("Provide one of pdf_path, zip_path, or input_path.")
    if provided > 1:
        raise ValueError("Only one of pdf_path, zip_path, or input_path can be specified.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reporter = ProgressReporter(progress_callback)
    cost_tracker = CostTracker(pricing=config.pricing_dict())
    result_path = output_path.parent / f"{output_path.stem}_result.json"
    cost_path = output_path.parent / f"{output_path.stem}_cost.json"

    if input_path:
        tree, pages, doc_name, tree_path, sections = _prepare_md_input(
            md_path=Path(input_path),
            config=config,
            skip_index=skip_index,
            reporter=reporter,
        )
    elif zip_path:
        tree, pages, doc_name, tree_path, sections = _prepare_zip_input(
            zip_path=Path(zip_path),
            config=config,
            skip_index=skip_index,
            reporter=reporter,
        )
    else:
        tree, pages, doc_name, tree_path, sections = _prepare_pdf_input(
            pdf_path=Path(pdf_path),
            config=config,
            skip_index=skip_index,
            reporter=reporter,
        )

    if skip_analysis and result_path.exists():
        reporter.emit(
            "analyzing_sections",
            "completed",
            "Reusing saved analysis",
            detail=result_path.name,
        )
        reporter.emit(
            "correlating_findings",
            "completed",
            "Reusing saved synthesis",
            detail=result_path.name,
        )
        result = AnalysisResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    else:
        reporter.emit(
            "analyzing_sections",
            "running",
            "Analyzing sections",
            detail=f"{len(sections)} sections discovered",
            current=0,
            total=len(sections),
        )
        result = run_analysis(
            config=config,
            tree=tree,
            pages=pages,
            sections=sections,
            skills_dir=skills_dir or _default_skills_dir(),
            cost_tracker=cost_tracker,
            verbose=verbose,
            progress_callback=progress_callback,
        )
        result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    reporter.emit("generating_excel", "running", "Generating Excel workbook")
    excel_generator.generate(result, output_path, tree=tree)
    reporter.emit(
        "generating_excel",
        "completed",
        "Excel workbook ready",
        detail=output_path.name,
        percent=100,
    )

    cost_tracker.save(cost_path, pdf_name=doc_name)
    reporter.emit(
        "completed",
        "completed",
        "Analysis complete",
        detail=output_path.name,
        percent=100,
    )

    artifacts = PipelineArtifacts(
        output_path=output_path,
        result_path=result_path,
        cost_path=cost_path,
        tree_path=tree_path,
        doc_name=doc_name,
    )
    return result, cost_tracker, artifacts


def _default_skills_dir() -> Path:
    """Resolve skills directory relative to this package."""
    # backend/ewa_pipeline/services/pipeline.py → backend/skills
    backend_dir = Path(__file__).resolve().parent.parent.parent
    return backend_dir / "skills"


def _prepare_md_input(
    *,
    md_path: Path,
    config: Config,
    skip_index: bool,
    reporter: ProgressReporter,
) -> tuple[dict, dict[int, str], str, Path, list]:
    """Prepare pipeline input from a pre-existing markdown file."""
    from ewa_pipeline.indexer.tree_builder import build_document_tree_from_md

    data_dir = md_path.parent
    tree_path = data_dir / f"{md_path.stem}_tree.json"

    reporter.emit(
        "normalizing_document",
        "completed",
        "Markdown loaded",
        detail=md_path.name,
    )

    if skip_index and tree_path.exists():
        reporter.emit(
            "building_tree",
            "completed",
            "Reusing document structure",
            detail=tree_path.name,
        )
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
    else:
        reporter.emit(
            "building_tree",
            "running",
            "Building document structure",
            detail=md_path.name,
        )
        tree = build_document_tree_from_md(md_path, config, data_dir)
        reporter.emit(
            "building_tree",
            "completed",
            "Document structure ready",
            detail=tree_path.name,
        )

    sections = get_analyzable_sections(tree)
    reporter.emit(
        "discovering_sections",
        "completed",
        "Sections discovered",
        detail=f"{len(sections)} sections ready",
        current=len(sections),
        total=len(sections) or 1,
    )
    return tree, {}, md_path.stem, tree_path, sections


def _prepare_zip_input(
    *,
    zip_path: Path,
    config: Config,
    skip_index: bool,
    reporter: ProgressReporter,
) -> tuple[dict, dict[int, str], str, Path, list]:
    from ewa_pipeline.indexer.html_parser import parse_html_to_markdown
    from ewa_pipeline.indexer.tree_builder import build_document_tree_from_md
    from ewa_pipeline.indexer.zip_extractor import extract_ewa_zip

    data_dir = zip_path.parent
    extract_dir = data_dir / f"{zip_path.stem}_html"
    reporter.emit("extracting_input", "running", "Extracting ZIP archive", detail=zip_path.name)
    html_path, _ = extract_ewa_zip(zip_path, extract_dir)
    reporter.emit("extracting_input", "completed", "ZIP extracted", detail=html_path.name)

    md_path = data_dir / f"{html_path.stem}.md"
    tree_path = data_dir / f"{html_path.stem}_tree.json"
    if skip_index and md_path.exists():
        reporter.emit("normalizing_document", "completed", "Reusing markdown", detail=md_path.name)
    else:
        reporter.emit("normalizing_document", "running", "Converting HTML to markdown", detail=html_path.name)
        _, saved_md = parse_html_to_markdown(html_path, data_dir)
        md_path = saved_md
        tree_path = data_dir / f"{saved_md.stem}_tree.json"
        reporter.emit("normalizing_document", "completed", "Markdown ready", detail=saved_md.name)

    if skip_index and tree_path.exists():
        reporter.emit("building_tree", "completed", "Reusing document structure", detail=tree_path.name)
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
    else:
        reporter.emit("building_tree", "running", "Building document structure", detail=md_path.name)
        tree = build_document_tree_from_md(md_path, config, data_dir)
        reporter.emit("building_tree", "completed", "Document structure ready", detail=tree_path.name)

    sections = get_analyzable_sections(tree)
    reporter.emit(
        "discovering_sections",
        "completed",
        "Sections discovered",
        detail=f"{len(sections)} sections ready",
        current=len(sections),
        total=len(sections) or 1,
    )
    return tree, {}, html_path.stem, tree_path, sections


def _prepare_pdf_input(
    *,
    pdf_path: Path,
    config: Config,
    skip_index: bool,
    reporter: ProgressReporter,
) -> tuple[dict, dict[int, str], str, Path, list]:
    from ewa_pipeline.indexer.pdf_parser import parse_pdf_to_pages
    from ewa_pipeline.indexer.tree_builder import build_document_tree

    data_dir = pdf_path.parent
    tree_path = data_dir / f"{pdf_path.stem}_tree.json"

    reporter.emit("normalizing_document", "running", "Parsing PDF into pages", detail=pdf_path.name)
    pages = parse_pdf_to_pages(pdf_path)
    reporter.emit(
        "normalizing_document",
        "completed",
        "PDF parsed",
        detail=f"{len(pages)} pages extracted",
        current=len(pages),
        total=len(pages) or 1,
    )

    if skip_index and tree_path.exists():
        reporter.emit("building_tree", "completed", "Reusing document structure", detail=tree_path.name)
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
    else:
        reporter.emit("building_tree", "running", "Building document structure", detail=pdf_path.name)
        tree = build_document_tree(pdf_path, config, data_dir)
        reporter.emit("building_tree", "completed", "Document structure ready", detail=tree_path.name)

    sections = get_analyzable_sections(tree)
    reporter.emit(
        "discovering_sections",
        "completed",
        "Sections discovered",
        detail=f"{len(sections)} sections ready",
        current=len(sections),
        total=len(sections) or 1,
    )
    return tree, pages, pdf_path.stem, tree_path, sections
