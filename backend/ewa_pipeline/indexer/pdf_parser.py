from pathlib import Path
import pymupdf4llm


def parse_pdf_to_pages(pdf_path: Path) -> dict[int, str]:
    """
    Parse PDF into a 1-indexed dict of {page_number: markdown_text}.
    Page 1 = first page of the document (matches PageIndex start_index/end_index).
    """
    chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
    # chunks is a list ordered by page; we map to 1-based page numbers
    return {i + 1: chunk["text"] for i, chunk in enumerate(chunks)}


def parse_pdf_to_markdown(pdf_path: Path, output_dir: Path) -> tuple[str, Path]:
    """Convert PDF to a single markdown file. Returns (markdown_text, saved_path)."""
    pages = parse_pdf_to_pages(pdf_path)
    markdown = "\n\n".join(pages[p] for p in sorted(pages))
    md_path = output_dir / f"{pdf_path.stem}.md"
    md_path.write_text(markdown, encoding="utf-8")
    return markdown, md_path
