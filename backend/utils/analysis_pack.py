from __future__ import annotations

import re
from typing import Any, Dict, List

from utils.parameter_extractor import extract_parameters_from_markdown


_HEADER_PATTERN = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
_MAX_SUMMARY_CHARS = 2400
_MAX_SEARCH_RESULTS = 8
_MAX_SECTION_PREVIEW_CHARS = 800
_PARAMETER_KEYWORDS = (
    "parameter",
    "profile",
    "configuration",
    "setting",
    "recommended",
    "current value",
    "target value",
    "hana",
    "kernel",
    "memory",
    "buffer",
    "abap/",
    "rdisp",
    "rsdb",
    "icm/",
    "global.ini",
    "indexserver.ini",
    "daemon.ini",
)


def build_analysis_pack(
    blob_name: str,
    markdown_content: str,
    metadata: Dict[str, Any] | None = None,
    check_overview_index: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    text = markdown_content or ""
    sections = _split_sections(text)
    document_stats = _build_document_stats(text, sections)
    parameter_sections = _build_parameter_sections(sections)
    parameter_focus_markdown = _build_parameter_focus_markdown(parameter_sections)
    parameter_candidates = extract_parameters_from_markdown(parameter_focus_markdown or text)

    pack = {
        "version": "1.0",
        "blob_name": blob_name,
        "metadata": metadata or {},
        "document_stats": document_stats,
        "summary": _build_summary(text, sections, check_overview_index, parameter_sections),
        "sections": sections,
        "section_lookup": {section["id"]: section["title"] for section in sections},
        "parameter_sections": parameter_sections,
        "parameter_focus_markdown": parameter_focus_markdown,
        "parameter_candidates": parameter_candidates,
        "check_overview": check_overview_index or {"rows": []},
        "page_map": _build_page_map(sections),
    }
    return pack


def get_analysis_pack_summary(analysis_pack: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "blob_name": analysis_pack.get("blob_name"),
        "metadata": analysis_pack.get("metadata", {}),
        "document_stats": analysis_pack.get("document_stats", {}),
        "summary": analysis_pack.get("summary", {}),
        "section_count": len(analysis_pack.get("sections", [])),
        "parameter_section_count": len(analysis_pack.get("parameter_sections", [])),
        "check_overview_rows": len((analysis_pack.get("check_overview") or {}).get("rows", [])),
    }


def list_sections(analysis_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    sections = analysis_pack.get("sections", [])
    return [
        {
            "id": section.get("id"),
            "title": section.get("title"),
            "level": section.get("level"),
            "start_line": section.get("start_line"),
            "end_line": section.get("end_line"),
            "char_count": section.get("char_count"),
            "preview": section.get("preview"),
            "is_parameter_section": section.get("is_parameter_section", False),
        }
        for section in sections
    ]


def get_section(analysis_pack: Dict[str, Any], section_id: str) -> Dict[str, Any]:
    for section in analysis_pack.get("sections", []):
        if section.get("id") == section_id:
            return section
    raise KeyError(f"Section not found: {section_id}")


def search_sections(analysis_pack: Dict[str, Any], query: str, limit: int = _MAX_SEARCH_RESULTS) -> List[Dict[str, Any]]:
    if not query or not query.strip():
        return []

    tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9_/.-]+", query) if token.strip()]
    if not tokens:
        return []

    ranked: List[Dict[str, Any]] = []
    for section in analysis_pack.get("sections", []):
        haystack = f"{section.get('title', '')}\n{section.get('content', '')}".lower()
        score = sum(haystack.count(token) for token in tokens)
        if score <= 0:
            continue
        ranked.append(
            {
                "section_id": section.get("id"),
                "title": section.get("title"),
                "score": score,
                "preview": _build_search_preview(section.get("content", ""), tokens),
                "is_parameter_section": section.get("is_parameter_section", False),
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["title"]))
    return ranked[: max(1, limit)]


def get_parameter_sections(analysis_pack: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sections": analysis_pack.get("parameter_sections", []),
        "parameter_focus_markdown": analysis_pack.get("parameter_focus_markdown", ""),
        "parameter_candidates": analysis_pack.get("parameter_candidates", []),
    }


def get_check_overview_rows(analysis_pack: Dict[str, Any]) -> Dict[str, Any]:
    return analysis_pack.get("check_overview", {"rows": []})


def _split_sections(markdown_content: str) -> List[Dict[str, Any]]:
    matches = list(_HEADER_PATTERN.finditer(markdown_content))
    if not matches:
        line_count = len(markdown_content.splitlines())
        return [
            {
                "id": "section-01",
                "title": "Document",
                "level": 1,
                "start_line": 1,
                "end_line": max(1, line_count),
                "char_count": len(markdown_content),
                "preview": markdown_content[:_MAX_SECTION_PREVIEW_CHARS],
                "content": markdown_content.strip(),
                "is_parameter_section": _is_parameter_section("Document", markdown_content),
            }
        ]

    lines = markdown_content.splitlines()
    sections: List[Dict[str, Any]] = []
    for index, match in enumerate(matches, start=1):
        title = match.group(2).strip()
        start_offset = match.end()
        end_offset = matches[index].start() if index < len(matches) else len(markdown_content)
        content = markdown_content[start_offset:end_offset].strip()
        start_line = markdown_content[: match.start()].count("\n") + 1
        end_line = markdown_content[: end_offset].count("\n") + 1
        sections.append(
            {
                "id": f"section-{index:02d}",
                "title": title,
                "level": len(match.group(1)),
                "start_line": start_line,
                "end_line": end_line,
                "char_count": len(content),
                "preview": content[:_MAX_SECTION_PREVIEW_CHARS],
                "content": content,
                "is_parameter_section": _is_parameter_section(title, content),
            }
        )
    return sections


def _build_document_stats(markdown_content: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    lines = markdown_content.splitlines()
    words = re.findall(r"\S+", markdown_content)
    return {
        "characters": len(markdown_content),
        "lines": len(lines),
        "words": len(words),
        "sections": len(sections),
        "parameter_sections": sum(1 for section in sections if section.get("is_parameter_section")),
    }


def _build_summary(
    markdown_content: str,
    sections: List[Dict[str, Any]],
    check_overview_index: Dict[str, Any] | None,
    parameter_sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    preview = markdown_content[:_MAX_SUMMARY_CHARS]
    return {
        "document_preview": preview,
        "section_titles": [section.get("title") for section in sections[:25]],
        "parameter_section_titles": [section.get("title") for section in parameter_sections[:12]],
        "check_overview_row_count": len((check_overview_index or {}).get("rows", [])),
    }


def _build_parameter_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for section in sections:
        if not section.get("is_parameter_section"):
            continue
        result.append(
            {
                "id": section.get("id"),
                "title": section.get("title"),
                "level": section.get("level"),
                "start_line": section.get("start_line"),
                "end_line": section.get("end_line"),
                "char_count": section.get("char_count"),
                "preview": section.get("preview"),
                "content": section.get("content"),
            }
        )
    return result


def _build_parameter_focus_markdown(parameter_sections: List[Dict[str, Any]]) -> str:
    if not parameter_sections:
        return ""

    chunks: List[str] = []
    for section in parameter_sections:
        level = max(1, min(int(section.get("level", 2)), 4))
        heading = "#" * level
        chunks.append(f"{heading} {section.get('title', 'Section')}")
        content = section.get("content", "")
        if content:
            chunks.append(content)
        chunks.append("")
    return "\n".join(chunks).strip()


def _build_page_map(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "section_id": section.get("id"),
            "title": section.get("title"),
            "start_line": section.get("start_line"),
            "end_line": section.get("end_line"),
        }
        for section in sections
    ]


def _is_parameter_section(title: str, content: str) -> bool:
    haystack = f"{title}\n{content}".lower()
    return any(keyword in haystack for keyword in _PARAMETER_KEYWORDS)


def _build_search_preview(content: str, tokens: List[str]) -> str:
    if not content:
        return ""
    content_lower = content.lower()
    first_match = min((content_lower.find(token) for token in tokens if token in content_lower), default=-1)
    if first_match == -1:
        return content[:_MAX_SECTION_PREVIEW_CHARS]
    start = max(0, first_match - 180)
    end = min(len(content), first_match + 420)
    return content[start:end].strip()
