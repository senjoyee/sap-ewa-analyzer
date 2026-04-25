import asyncio
import json
from pathlib import Path

from ewa_pipeline.config import Config


def build_document_tree(pdf_path: Path, config: Config, output_dir: Path) -> dict:
    """
    Build hierarchical PageIndex tree locally using LiteLLM (azure/gpt-5.4-nano).
    Returns the full result dict: {"doc_name", "structure", "doc_description"}.
    Saves to output_dir/{pdf_stem}_tree.json.
    """
    from pageindex import page_index

    result = page_index(
        doc=str(pdf_path),
        model=config.pageindex.model,
        max_page_num_each_node=config.pageindex.max_pages_per_node,
        max_token_num_each_node=config.pageindex.max_tokens_per_node,
        if_add_node_id="yes",
        if_add_node_summary="yes" if config.pageindex.add_node_summary else "no",
        if_add_doc_description="yes" if config.pageindex.add_doc_description else "no",
        if_add_node_text="no",
    )

    tree_path = output_dir / f"{pdf_path.stem}_tree.json"
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


def build_document_tree_from_md(md_path: Path, config: Config, output_dir: Path) -> dict:
    """
    Build hierarchical PageIndex tree from a Markdown file using md_to_tree.

    Uses the same LiteLLM model as the PDF pipeline (azure/gpt-5.4-nano).
    Node text is always preserved in the tree so get_node_content() can extract
    section content without a separate pages dict.

    Saves tree to output_dir/{md_stem}_tree.json.
    Returns the tree dict.
    """
    from pageindex import md_to_tree

    result = asyncio.run(
        md_to_tree(
            md_path=str(md_path),
            if_thinning=False,
            if_add_node_summary="yes" if config.pageindex.add_node_summary else "no",
            summary_token_threshold=200,
            model=config.pageindex.model,
            if_add_doc_description="yes" if config.pageindex.add_doc_description else "no",
            if_add_node_text="yes",   # always keep text — needed by get_node_content()
            if_add_node_id="yes",
        )
    )

    tree_path = output_dir / f"{md_path.stem}_tree.json"
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result
