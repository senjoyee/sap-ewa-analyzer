"""Chapter dispatcher for routing EWA chapters to domain specialists.

Primary strategy: every chapter is routed via a fast LLM (gpt-5.4-nano by default)
using parallel async calls so total added latency ≈ one round-trip regardless of
chapter count.

Fallback strategy (no AI client available, e.g. offline tests): static table keyed
by chapter number, calibrated against the SHP/HANA EWA variant. Chapters not in the
table default to "lifecycle".

Returns both the domain→chapters mapping AND a routing_map dict that records, per
chapter, the title, assigned domain, confidence, and routing source.  This is
persisted as a diagnostic blob by the workflow orchestrator.
"""
from __future__ import annotations

import json
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.ewa_slicer import ChapterData

logger = logging.getLogger(__name__)

ALL_DOMAINS = ["security", "database", "performance", "basis", "business", "lifecycle"]

# ---------------------------------------------------------------------------
# Static fallback table: chapter number -> domain name
# Used ONLY when no AI client is available (offline / test environments).
# Do NOT use this as the primary routing path — chapter numbers vary across
# SAP system types (ECC, BW, Gateway, S/4HANA, TP, ECP, etc.).
# ---------------------------------------------------------------------------
_STATIC_FALLBACK: dict[int, str] = {
    1:  "lifecycle",
    2:  "lifecycle",
    3:  "basis",
    4:  "lifecycle",
    5:  "performance",
    6:  "business",
    7:  "performance",
    8:  "performance",
    9:  "performance",
    10: "basis",
    11: "security",
    12: "basis",
    13: "business",
    14: "business",
    15: "lifecycle",
    16: "lifecycle",
    17: "lifecycle",
    18: "database",
    19: "database",
    20: "basis",
    21: "basis",
    22: "business",
    23: "performance",
}


def _load_router_prompt() -> str:
    """Load the router system prompt from the external prompt file."""
    prompt_file = Path(__file__).parent.parent / "prompts" / "router_system_prompt.md"
    try:
        return prompt_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.error("Router prompt file not found at %s", prompt_file)
        raise


_AI_ROUTER_SYSTEM_PROMPT = _load_router_prompt()


@dataclass
class RoutingEntry:
    """Record of how a single chapter was routed."""
    chapter_number: int
    title: str
    domain: str
    source: str          # "llm" | "static_fallback" | "static_fallback_default"
    confidence: float = 1.0
    static_candidate: str | None = None  # set when LLM overrides the static table

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "chapter": self.chapter_number,
            "title": self.title,
            "domain": self.domain,
            "source": self.source,
            "confidence": round(self.confidence, 3),
        }
        if self.static_candidate and self.static_candidate != self.domain:
            d["static_candidate"] = self.static_candidate
        return d


async def dispatch_chapters(
    chapters: dict[int, ChapterData],
    ai_client: Any = None,
    router_model: str = "gpt-5.4-nano",
    provider: str = "openai",
) -> tuple[dict[str, list[ChapterData]], dict[int, RoutingEntry]]:
    """Route every chapter to a domain.

    Returns:
        (domain_chapters, routing_map)
        - domain_chapters: dict mapping domain name -> list of ChapterData
        - routing_map: dict mapping chapter number -> RoutingEntry (for diagnostics)

    Chapters with number 0 (preamble) are skipped.
    When an AI client is available, ALL chapters are routed via parallel LLM calls.
    When no AI client is available, the static fallback table is used.
    """
    result: dict[str, list[ChapterData]] = {d: [] for d in ALL_DOMAINS}
    routing_map: dict[int, RoutingEntry] = {}

    numbered = {num: ch for num, ch in chapters.items() if num != 0}
    if 0 in chapters:
        logger.debug("Skipping preamble (chapter 0)")

    if ai_client:
        # Primary path: parallel LLM routing for all chapters
        logger.info("[DISPATCH] Routing %d chapters via LLM (model=%s)", len(numbered), router_model)
        tasks = {
            num: _ai_route_chapter(ch, ai_client, router_model, provider=provider)
            for num, ch in numbered.items()
        }
        llm_results = dict(
            zip(tasks.keys(), await asyncio.gather(*tasks.values(), return_exceptions=True))
        )
        for num, ch in numbered.items():
            llm_out = llm_results[num]
            static_candidate = _STATIC_FALLBACK.get(num)
            if isinstance(llm_out, Exception):
                # LLM call failed — fall back to static table
                domain = static_candidate or "lifecycle"
                source = "static_fallback" if static_candidate else "static_fallback_default"
                confidence = 0.0
                logger.warning(
                    "[DISPATCH] LLM failed for ch %d (%s), using %s (%s): %s",
                    num, ch.title, domain, source, llm_out,
                )
            else:
                domain, confidence = llm_out
                source = "llm"
                if static_candidate and static_candidate != domain:
                    logger.info(
                        "[DISPATCH] Ch %d (%s): LLM->%s overrides static->%s (conf=%.2f)",
                        num, ch.title, domain, static_candidate, confidence,
                    )
            result[domain].append(ch)
            routing_map[num] = RoutingEntry(
                chapter_number=num,
                title=ch.title,
                domain=domain,
                source=source,
                confidence=confidence,
                static_candidate=static_candidate,
            )
            logger.debug("[DISPATCH] Ch %d (%s) -> %s [%s]", num, ch.title, domain, source)
    else:
        # Offline fallback: static table only
        logger.warning(
            "[DISPATCH] No AI client — using static fallback table for all %d chapters", len(numbered)
        )
        for num, ch in numbered.items():
            domain = _STATIC_FALLBACK.get(num, "lifecycle")
            source = "static_fallback" if num in _STATIC_FALLBACK else "static_fallback_default"
            result[domain].append(ch)
            routing_map[num] = RoutingEntry(
                chapter_number=num,
                title=ch.title,
                domain=domain,
                source=source,
                confidence=1.0,
            )

    # Log routing summary
    for domain in ALL_DOMAINS:
        ch_nums = sorted(ch.number for ch in result[domain])
        if ch_nums:
            logger.info("[DISPATCH] %-12s: chapters %s", domain, ch_nums)

    return result, routing_map


async def _ai_route_chapter(
    chapter: ChapterData,
    ai_client: Any,
    model: str,
    provider: str = "openai",
) -> tuple[str, float]:
    """Use a fast LLM to classify a chapter. Returns (domain, confidence).

    Raises on failure so the caller can apply its own fallback logic.
    """
    # Use a larger preview so routing relies on stronger evidence than title keywords alone.
    preview = chapter.raw_content[:1200]
    user_msg = f"Chapter title: {chapter.title}\nContent preview: {preview}"

    if provider == "anthropic":
        response = await asyncio.to_thread(
            lambda: ai_client.messages.create(
                model=model,
                max_tokens=100,
                system=_AI_ROUTER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                stream=False,
            )
        )
        parts: list[str] = []
        for block in (getattr(response, "content", None) or []):
            if getattr(block, "type", None) == "text":
                t = getattr(block, "text", None)
                if t:
                    parts.append(t)
        text = "".join(parts).strip()
    else:
        response = await asyncio.to_thread(
            lambda: ai_client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": _AI_ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_output_tokens=100,
            )
        )
        text = response.output_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    parsed = json.loads(text)
    domain = parsed.get("domain", "").lower()
    confidence = float(parsed.get("confidence", 0.0))

    if domain in ALL_DOMAINS and confidence >= 0.70:
        return domain, confidence

    # Low confidence — fall back to static table candidate, then lifecycle
    fallback = _STATIC_FALLBACK.get(chapter.number, "lifecycle")
    logger.warning(
        "[DISPATCH] Low-confidence result for ch %d (%s): domain=%s conf=%.2f -> using %s",
        chapter.number, chapter.title, domain, confidence, fallback,
    )
    return fallback, confidence
