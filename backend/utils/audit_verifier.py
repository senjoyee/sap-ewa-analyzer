"""
Audit trail verification for v2.0 pillar-based EWA analysis.

Compares the TOC Health Map (RED/YELLOW counts) against the findings
actually routed into pillars.  Produces / updates the ``Audit Trail``
block in the JSON output.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def verify_coverage(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute ``Audit Trail`` based on TOC Health Map vs. pillar findings.

    The LLM is instructed to produce its own audit trail, but this function
    recalculates independently so we can trust the numbers.

    Returns the (mutated) *data* dict.
    """
    toc = data.get("TOC Health Map")
    if not isinstance(toc, list):
        logger.warning("No TOC Health Map found; skipping audit verification")
        return data

    # Count RED and YELLOW chapters
    red_yellow_chapters: List[str] = []
    for entry in toc:
        status = (entry.get("status") or "").upper()
        if status in ("RED", "YELLOW"):
            red_yellow_chapters.append(entry.get("chapter", "unknown"))

    red_yellow_total = len(red_yellow_chapters)

    # Collect all finding Areas/Finding texts across pillars for matching
    pillars = data.get("Pillars", {})
    if not isinstance(pillars, dict):
        pillars = {}

    mapped_chapters: set[str] = set()
    for _pillar_key, bucket in pillars.items():
        if not isinstance(bucket, dict):
            continue
        for finding in bucket.get("findings", []):
            # Use Area and Finding to match against chapter names
            area = (finding.get("Area") or "").lower()
            finding_text = (finding.get("Finding") or "").lower()
            for chapter in red_yellow_chapters:
                chapter_lower = chapter.lower()
                if area and area in chapter_lower:
                    mapped_chapters.add(chapter)
                elif finding_text and finding_text in chapter_lower:
                    mapped_chapters.add(chapter)
                elif chapter_lower and (chapter_lower in area or chapter_lower in finding_text):
                    mapped_chapters.add(chapter)

    red_yellow_mapped = len(mapped_chapters)
    unmapped = [ch for ch in red_yellow_chapters if ch not in mapped_chapters]
    coverage_pct = (red_yellow_mapped / red_yellow_total * 100) if red_yellow_total > 0 else 100.0

    audit_trail = {
        "red_yellow_total": red_yellow_total,
        "red_yellow_mapped": red_yellow_mapped,
        "unmapped_chapters": unmapped,
        "coverage_pct": round(coverage_pct, 1),
    }

    data["Audit Trail"] = audit_trail

    logger.info(
        "Audit Trail: %d/%d mapped (%.1f%%), %d unmapped",
        red_yellow_mapped,
        red_yellow_total,
        coverage_pct,
        len(unmapped),
    )

    return data
