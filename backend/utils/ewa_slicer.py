"""Deterministic markdown slicer for SAP EWA reports.

Splits a full EWA markdown document into individual chapters and subsections
using regex scanning of # and ## headings. No LLM calls.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Matches chapter headings like "# 1 Service Summary" or "# 23 Trend Analysis"
_CHAPTER_RE = re.compile(r"^#\s+(\d+)\s+(.*)", re.MULTILINE)

# Matches numbered subsections like "## 4.1 SAP Application Release" or "## 19.8 Top Statements"
# Also matches unnumbered subsections like "## Performance Indicators for SHP"
_SUBSECTION_RE = re.compile(r"^##\s+(?:(\d+\.\d+)\s+)?(.*)", re.MULTILINE)


@dataclass
class ChapterData:
    """Represents a single chapter from the EWA markdown."""
    number: int
    title: str
    raw_content: str
    subsections: list[tuple[str, str]] = field(default_factory=list)
    # (subsection_title, subsection_content) — title includes the number if present


def slice_chapters(markdown: str) -> dict[int, ChapterData]:
    """Parse EWA markdown into a dict keyed by chapter number.

    Chapter 0 is the preamble (cover page content before the first numbered chapter).
    """
    chapters: dict[int, ChapterData] = {}

    # Find all chapter boundaries
    chapter_matches = list(_CHAPTER_RE.finditer(markdown))

    if not chapter_matches:
        logger.warning("No chapter headings found in markdown (%d chars)", len(markdown))
        chapters[0] = ChapterData(number=0, title="Preamble", raw_content=markdown)
        return chapters

    # Preamble: everything before the first chapter heading
    preamble_end = chapter_matches[0].start()
    if preamble_end > 0:
        preamble_text = markdown[:preamble_end].strip()
        if preamble_text:
            chapters[0] = ChapterData(number=0, title="Preamble", raw_content=preamble_text)

    # Extract each chapter's content
    for i, match in enumerate(chapter_matches):
        chapter_num = int(match.group(1))
        chapter_title = match.group(2).strip()
        content_start = match.end()
        content_end = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(markdown)
        raw_content = markdown[content_start:content_end].strip()

        # Parse subsections within this chapter
        subsections = _extract_subsections(raw_content)

        chapters[chapter_num] = ChapterData(
            number=chapter_num,
            title=chapter_title,
            raw_content=raw_content,
            subsections=subsections,
        )

    logger.info("Sliced markdown into %d chapters (excl. preamble)", len(chapters) - (0 in chapters))
    return chapters


def _extract_subsections(chapter_content: str) -> list[tuple[str, str]]:
    """Extract subsections from chapter content using ## headings."""
    subsections: list[tuple[str, str]] = []
    matches = list(_SUBSECTION_RE.finditer(chapter_content))

    if not matches:
        return subsections

    for i, match in enumerate(matches):
        sub_number = match.group(1) or ""  # e.g. "4.1" or "" for unnumbered
        sub_title = match.group(2).strip()
        full_title = f"{sub_number} {sub_title}".strip() if sub_number else sub_title
        content_start = match.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(chapter_content)
        sub_content = chapter_content[content_start:content_end].strip()
        subsections.append((full_title, sub_content))

    return subsections


def truncate_large_chapter(chapter: ChapterData, char_limit: int = 8000) -> ChapterData:
    """Truncate oversized chapters (e.g., chapter 19 with ~4000 lines of SQL).

    Preserves the overview (content before the first ## heading) and replaces
    the rest with a truncation notice. Returns a new ChapterData; does not
    mutate the original.
    """
    if len(chapter.raw_content) <= char_limit:
        return chapter

    n_subs = len(chapter.subsections)
    logger.info(
        "Truncating chapter %d (%s): %d chars -> %d limit, %d subsections",
        chapter.number, chapter.title, len(chapter.raw_content), char_limit, n_subs,
    )

    # Extract overview: content before the first ## heading
    first_sub = _SUBSECTION_RE.search(chapter.raw_content)
    if first_sub:
        overview = chapter.raw_content[:first_sub.start()].strip()
    else:
        overview = chapter.raw_content[:char_limit]

    # Ensure overview itself doesn't exceed the limit
    if len(overview) > char_limit:
        overview = overview[:char_limit]

    truncation_notice = (
        f"\n\n[TRUNCATED: {n_subs} subsections found in this chapter. "
        f"Refer to the original EWA report for full details.]"
    )

    return ChapterData(
        number=chapter.number,
        title=chapter.title,
        raw_content=overview + truncation_notice,
        subsections=[("__truncated__", f"{n_subs} subsections")],
    )
