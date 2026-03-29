"""Hybrid dispatcher for routing EWA chapters to domain specialists.

Uses a static routing table for known chapter numbers and falls back to
an LLM-based router (gpt-5.4-nano) for unrecognized chapters.
"""
from __future__ import annotations

import json
import asyncio
import logging
from typing import Any

from utils.ewa_slicer import ChapterData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static routing table: chapter number -> domain name
# ---------------------------------------------------------------------------
DOMAIN_ROUTES: dict[int, str] = {
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

ALL_DOMAINS = ["security", "database", "performance", "basis", "business", "lifecycle"]

_AI_ROUTER_SYSTEM_PROMPT = """\
You are a chapter classification specialist for SAP EarlyWatch Alert reports.
Given a chapter title and a short content preview, classify it into exactly one domain.

Respond with a JSON object:
{"domain": "<one of: security, database, performance, basis, business, lifecycle>", "confidence": <float 0.0-1.0>}

Domains:
- security: Passwords, authorizations, SAP_ALL, RFC/ICF security, TLS, patch vulnerabilities
- database: HANA config, SQL performance, disk/memory, backups, DB stability
- performance: Response times, workload, hardware capacity, CPU/memory utilization, trends
- basis: System operations, transports, ABAP dumps, number ranges, availability, Gateway, Fiori ops
- business: Financial data, DVM, key figures, business process analytics, reconciliation
- lifecycle: Software versions, maintenance phases, kernel/OS/DB end-of-life, upgrades, landscape

Return ONLY the JSON object, no other text."""


async def dispatch_chapters(
    chapters: dict[int, ChapterData],
    ai_client: Any = None,
    router_model: str = "gpt-5.4-nano",
    provider: str = "openai",
) -> dict[str, list[ChapterData]]:
    """Route each chapter to a domain. Returns dict keyed by domain name.

    Chapters with number 0 (preamble) are skipped.
    Unknown chapter numbers are routed via LLM; on failure → lifecycle.
    """
    result: dict[str, list[ChapterData]] = {d: [] for d in ALL_DOMAINS}
    ai_calls: list[tuple[int, ChapterData]] = []

    for num, chapter in chapters.items():
        if num == 0:
            logger.debug("Skipping preamble (chapter 0)")
            continue

        domain = DOMAIN_ROUTES.get(num)
        if domain:
            result[domain].append(chapter)
            logger.debug("Chapter %d -> %s (static)", num, domain)
        else:
            ai_calls.append((num, chapter))
            logger.info("Chapter %d (%s) not in static table, queuing for AI routing", num, chapter.title)

    # Route unknown chapters via LLM
    if ai_calls and ai_client:
        for num, chapter in ai_calls:
            domain = await _ai_route_chapter(chapter, ai_client, router_model, provider=provider)
            result[domain].append(chapter)
            logger.info("Chapter %d -> %s (AI router)", num, domain)
    elif ai_calls:
        # No AI client available — fall back to lifecycle
        for num, chapter in ai_calls:
            logger.warning("No AI client for chapter %d (%s), defaulting to lifecycle", num, chapter.title)
            result["lifecycle"].append(chapter)

    # Log routing summary
    for domain in ALL_DOMAINS:
        ch_nums = [ch.number for ch in result[domain]]
        if ch_nums:
            logger.info("Domain %-12s: chapters %s", domain, ch_nums)

    return result


async def _ai_route_chapter(
    chapter: ChapterData,
    ai_client: Any,
    model: str,
    provider: str = "openai",
) -> str:
    """Use a fast LLM to classify an unknown chapter into a domain."""
    preview = chapter.raw_content[:500]
    user_msg = f"Chapter title: {chapter.title}\nContent preview: {preview}"

    try:
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
            # Extract text from Anthropic response
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

        if domain in ALL_DOMAINS and confidence >= 0.75:
            logger.info("AI routed chapter %d (%s) -> %s (confidence=%.2f)", chapter.number, chapter.title, domain, confidence)
            return domain

        logger.warning(
            "AI router low confidence for chapter %d: domain=%s, confidence=%.2f, falling back to lifecycle",
            chapter.number, domain, confidence,
        )
        return "lifecycle"

    except Exception:
        logger.exception("AI router failed for chapter %d (%s), falling back to lifecycle", chapter.number, chapter.title)
        return "lifecycle"
