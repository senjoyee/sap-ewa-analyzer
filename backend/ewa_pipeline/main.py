import json
import warnings
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console

# Suppress Pydantic serialization noise that fires on every LLM call when
# use_responses_api=True + with_structured_output(include_raw=True).
# The ParsedResponseOutputMessage union type generates a UserWarning for every
# possible union branch; the parsed output is correct regardless.
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
    module="pydantic",
)

console = Console()


def _load_env_and_config(config_path: str = "config.yaml"):
    load_dotenv()
    from ewa_pipeline.config import load_config
    return load_config(Path(config_path))


@click.group()
def cli():
    """EWA Deep Analyzer — SAP EarlyWatch Alert analysis pipeline."""


def _print_completion(result, cost_tracker, output_path: Path, doc_name: str) -> None:
    health_color = {"Critical": "red", "Warning": "yellow", "Healthy": "green"}.get(
        result.overall_system_health, "white"
    )
    total_cost = cost_tracker.to_dict(pdf_name=doc_name)["totals"]["cost_usd"]
    console.print(
        f"\n[bold green]Done![/bold green] "
        f"Overall health: [{health_color}]{result.overall_system_health}[/{health_color}] | "
        f"{sum(len(da.findings) for da in result.domain_analyses)} findings | "
        f"{len(result.cross_references)} cross-references\n"
        f"Report saved to: [bold]{output_path}[/bold]\n"
        f"Cost: ${total_cost:,.2f}"
    )


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--pdf", default=None, type=click.Path(exists=True), help="Path to EWA PDF")
@click.option("--zip", "zip_path", default=None, type=click.Path(exists=True),
              help="Path to EWA ZIP (HTML + icon assets)")
@click.option("--output", default="output/analysis.xlsx", show_default=True, help="Output Excel path")
@click.option("--config", "config_path", default="config.yaml", show_default=True, help="Config YAML path")
@click.option("--verbose", is_flag=True, help="Show detailed progress")
@click.option("--skip-index", is_flag=True, help="Reuse existing _tree.json if present")
@click.option("--skip-analysis", is_flag=True, help="Reuse existing _result.json (skip Phase 1+2 LLM calls)")
def analyze(pdf: str, zip_path: str, output: str, config_path: str, verbose: bool,
            skip_index: bool, skip_analysis: bool):
    """Run the full EWA analysis pipeline (Phase 0 + Phase 1 + Phase 2 + Excel).

    Accepts either a PDF (--pdf) or a ZIP containing an EWA HTML export (--zip).
    Exactly one of --pdf / --zip must be supplied.
    """
    if not pdf and not zip_path:
        raise click.UsageError("Provide either --pdf or --zip.")
    if pdf and zip_path:
        raise click.UsageError("Only one of --pdf or --zip can be specified.")

    config = _load_env_and_config(config_path)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from ewa_pipeline.services.pipeline import run_pipeline

    def _cli_progress(event):
        stage = event.stage.replace("_", " ").title()
        line = f"[cyan]{stage}[/cyan]: {event.label}"
        if event.detail:
            line += f" ({event.detail})"
        console.print(line)

    result, cost_tracker, artifacts = run_pipeline(
        config=config,
        output_path=output_path,
        pdf_path=Path(pdf) if pdf else None,
        zip_path=Path(zip_path) if zip_path else None,
        skip_index=skip_index,
        skip_analysis=skip_analysis,
        verbose=verbose,
        skills_dir=Path("skills"),
        progress_callback=_cli_progress,
    )
    console.print(f"  Result saved to [bold]{artifacts.result_path}[/bold]")
    console.print(f"  Cost report saved to [bold]{artifacts.cost_path}[/bold]")
    _print_completion(result, cost_tracker, output_path, artifacts.doc_name)


# ---------------------------------------------------------------------------
# excel  (unchanged)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--result", required=True, type=click.Path(exists=True),
              help="Path to _result.json from a previous run")
@click.option("--tree", "tree_path", required=True, type=click.Path(exists=True),
              help="Path to _tree.json from Phase 0")
@click.option("--output", default="output/analysis.xlsx", show_default=True, help="Output Excel path")
@click.option("--config", "config_path", default="config.yaml", show_default=True, help="Config YAML path")
def excel(result: str, tree_path: str, output: str, config_path: str):
    """Phase 3 only: regenerate Excel from a saved _result.json (no LLM calls for analysis)."""
    config = _load_env_and_config(config_path)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from ewa_pipeline.report import excel_generator
    from ewa_pipeline.report.schemas import AnalysisResult
    from ewa_pipeline.tracking.cost_tracker import CostTracker

    console.print(f"[cyan]Loading[/cyan]: {Path(result).name}")
    analysis_result = AnalysisResult.model_validate_json(Path(result).read_text(encoding="utf-8"))
    with open(tree_path, encoding="utf-8") as f:
        tree = json.load(f)

    cost_tracker = CostTracker(pricing=config.pricing_dict())
    cost_path = output_path.parent / f"{output_path.stem}_cost.json"

    console.print("[cyan]Phase 3[/cyan]: generating Excel workbook...")
    excel_generator.generate(analysis_result, output_path, tree=tree)

    cost_tracker.save(cost_path, pdf_name=Path(result).stem)
    console.print(f"  Cost report saved to [bold]{cost_path}[/bold]")

    health_color = {"Critical": "red", "Warning": "yellow", "Healthy": "green"}.get(
        analysis_result.overall_system_health, "white"
    )
    total_cost = cost_tracker.to_dict(pdf_name=Path(result).stem)["totals"]["cost_usd"]
    console.print(
        f"\n[bold green]Done![/bold green] "
        f"Overall health: [{health_color}]{analysis_result.overall_system_health}[/{health_color}] | "
        f"{sum(len(da.findings) for da in analysis_result.domain_analyses)} findings\n"
        f"Report saved to: [bold]{output_path}[/bold]\n"
        f"Cost: ${total_cost:,.2f}"
    )


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Host for the web app")
@click.option("--port", default=8000, show_default=True, type=int, help="Port for the web app")
def web(host: str, port: int):
    """Run the web UI and API."""
    import uvicorn

    uvicorn.run("ewa_analyzer.web:app", host=host, port=port, reload=False)


# ---------------------------------------------------------------------------
# index  (Phase 0 debug; supports both --pdf and --zip)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--pdf", default=None, type=click.Path(exists=True), help="Path to EWA PDF")
@click.option("--zip", "zip_path", default=None, type=click.Path(exists=True),
              help="Path to EWA ZIP (HTML + icon assets)")
@click.option("--config", "config_path", default="config.yaml", show_default=True, help="Config YAML path")
def index(pdf: str, zip_path: str, config_path: str):
    """Phase 0 only: parse document and build PageIndex tree (for debugging).

    Accepts either --pdf or --zip (exactly one required).
    """
    if not pdf and not zip_path:
        raise click.UsageError("Provide either --pdf or --zip.")
    if pdf and zip_path:
        raise click.UsageError("Only one of --pdf or --zip can be specified.")

    config = _load_env_and_config(config_path)

    from ewa_pipeline.indexer.tree_navigator import get_analyzable_sections, tree_to_summary

    if zip_path:
        from ewa_pipeline.indexer.zip_extractor import extract_ewa_zip
        from ewa_pipeline.indexer.html_parser import parse_html_to_markdown
        from ewa_pipeline.indexer.tree_builder import build_document_tree_from_md

        zip_file = Path(zip_path)
        data_dir = zip_file.parent
        extract_dir = data_dir / f"{zip_file.stem}_html"

        console.print(f"[cyan]Extracting[/cyan]: {zip_file.name}")
        html_path, _ = extract_ewa_zip(zip_file, extract_dir)
        console.print(f"  HTML file: {html_path.name}")

        console.print(f"[cyan]Converting[/cyan]: HTML → markdown...")
        _, saved_md = parse_html_to_markdown(html_path, data_dir)
        md_path = saved_md
        console.print(f"  Markdown: {saved_md}")

        console.print("[cyan]Indexing[/cyan]: building PageIndex tree from markdown (gpt-5.4-nano)...")
        tree = build_document_tree_from_md(md_path, config, data_dir)

    else:
        from ewa_pipeline.indexer.pdf_parser import parse_pdf_to_pages, parse_pdf_to_markdown
        from ewa_pipeline.indexer.tree_builder import build_document_tree

        pdf_path = Path(pdf)
        data_dir = pdf_path.parent

        console.print(f"[cyan]Parsing[/cyan]: {pdf_path.name}")
        pages = parse_pdf_to_pages(pdf_path)
        _, md_path = parse_pdf_to_markdown(pdf_path, data_dir)
        console.print(f"  {len(pages)} pages -> {md_path}")

        console.print("[cyan]Indexing[/cyan]: building PageIndex tree (gpt-5.4-nano)...")
        tree = build_document_tree(pdf_path, config, data_dir)

    sections = get_analyzable_sections(tree)
    console.print(f"  Analyzable sections: {len(sections)}")
    console.print(f"\n{tree_to_summary(tree)}")


if __name__ == "__main__":
    cli()
