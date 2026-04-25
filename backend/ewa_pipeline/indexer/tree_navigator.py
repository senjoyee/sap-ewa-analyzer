from dataclasses import dataclass, field


_SKIP_TITLES = {
    "table of contents", "toc", "contents", "cover page", "cover",
    "title page", "front matter", "index", "appendix",
}


@dataclass
class TreeNode:
    id: str
    title: str
    summary: str = ""
    page_start: int = 0
    page_end: int = 0
    level: int = 0
    children: list["TreeNode"] = field(default_factory=list)
    # Populated for markdown-based nodes (md_to_tree stores text directly in nodes).
    # Empty for PDF-based nodes, whose content is fetched via the pages dict.
    content: str = ""


def _node_id(raw_id) -> str:
    """Normalise node_id to a plain string.

    PageIndex stores node_id as a single-element list (e.g. ["0031"]).
    str(["0031"]) produces "['0031']" which breaks dict lookups when an LLM
    echoes the id back without the inner quotes.  Extract the first element
    so IDs are always clean strings like "0031".
    """
    if isinstance(raw_id, list):
        return str(raw_id[0]) if raw_id else ""
    return str(raw_id)


def _parse_node(raw: dict, level: int = 0) -> "TreeNode":
    node = TreeNode(
        id=_node_id(raw.get("node_id", "")),
        title=raw.get("title", ""),
        summary=raw.get("summary", raw.get("prefix_summary", "")),
        page_start=raw.get("start_index", 0),
        page_end=raw.get("end_index", 0),
        level=level,
        # "text" is present in markdown-based trees (md_to_tree with if_add_node_text="yes").
        # Absent in PDF-based trees, which use page ranges instead.
        content=raw.get("text", ""),
    )
    for child_raw in raw.get("nodes", []):
        node.children.append(_parse_node(child_raw, level + 1))
    return node


def flatten_tree(tree: dict) -> list[TreeNode]:
    """Return top-level nodes parsed from the PageIndex result dict."""
    return [_parse_node(raw, level=0) for raw in tree.get("structure", [])]


def _flatten_recursive(node: TreeNode) -> list[TreeNode]:
    result = [node]
    for child in node.children:
        result.extend(_flatten_recursive(child))
    return result


def get_analyzable_sections(tree: dict) -> list[TreeNode]:
    """Return all nodes (depth-first) excluding TOC/cover pages."""
    top_nodes = flatten_tree(tree)
    flat: list[TreeNode] = []
    for node in top_nodes:
        flat.extend(_flatten_recursive(node))

    seen: set[str] = set()
    result = []
    for node in flat:
        if node.id in seen:
            continue
        seen.add(node.id)
        if not node.title.strip():
            continue
        if node.title.lower().strip() in _SKIP_TITLES:
            continue
        result.append(node)
    return result


def get_node_content(pages: dict[int, str], node: TreeNode) -> str:
    """
    Extract content for a node.

    For markdown-based nodes (md_to_tree), content is stored directly in
    node.content — the pages dict is not needed and may be empty ({}).

    For PDF-based nodes, content is fetched from the 1-indexed pages dict
    using the node's page_start / page_end range.
    """
    # Markdown path: content is embedded in the node
    if node.content:
        return node.content

    # PDF path: look up page range
    start = node.page_start
    end = node.page_end

    if start <= 0 or end <= 0 or end < start:
        # Container/heading node with no direct content — return summary only
        return node.summary or ""

    parts = [pages[p] for p in range(start, end + 1) if p in pages]
    return "\n\n".join(parts)


def tree_to_summary(tree: dict) -> str:
    """Compact ~2K-token text summary of the tree structure."""
    nodes = get_analyzable_sections(tree)
    lines = [f"Document: {tree.get('doc_name', '')} ({len(nodes)} sections)"]
    if tree.get("doc_description"):
        lines.append(f"Description: {tree['doc_description'][:200]}")
    lines.append("")
    for node in nodes:
        indent = "  " * min(node.level, 4)
        snippet = node.summary[:80].replace("\n", " ") if node.summary else ""
        lines.append(
            f"{indent}[{node.id}] {node.title} "
            f"(pp.{node.page_start}-{node.page_end})"
            + (f": {snippet}" if snippet else "")
        )
    return "\n".join(lines)
