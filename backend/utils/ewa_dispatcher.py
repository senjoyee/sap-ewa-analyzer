"""Chapter dispatcher for routing EWA chapters to domain specialists.

Every chapter is routed via a fast LLM (gpt-5.4-nano by default) using parallel
async calls so total added latency ≈ one round-trip regardless of chapter count.

If any chapter fails to route the exception propagates and the workflow fails fast —
there is no static fallback path.

Returns both the domain→chapters mapping AND a routing_map dict that records, per
chapter, the title and assigned domain.  This is persisted as a diagnostic blob by
the workflow orchestrator.
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
    source: str = "llm"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter": self.chapter_number,
            "title": self.title,
            "domain": self.domain,
            "source": self.source,
        }


async def dispatch_chapters(
    chapters: dict[int, ChapterData],
    ai_client: Any,
    router_model: str = "gpt-5.4-nano",
    provider: str = "openai",
) -> tuple[dict[str, list[ChapterData]], dict[int, RoutingEntry]]:
    """Route every chapter to a domain via LLM.

    Returns:
        (domain_chapters, routing_map)
        - domain_chapters: dict mapping domain name -> list of ChapterData
        - routing_map: dict mapping chapter number -> RoutingEntry (for diagnostics)

    Chapters with number 0 (preamble) are skipped.
    All chapters are routed via parallel LLM calls.  Any failure raises immediately
    and the workflow aborts — there is no fallback.
    """
    if ai_client is None:
        raise ValueError(
            "dispatch_chapters requires an AI client — no fallback path is available"
        )

    result: dict[str, list[ChapterData]] = {d: [] for d in ALL_DOMAINS}
    routing_map: dict[int, RoutingEntry] = {}

    numbered = {num: ch for num, ch in chapters.items() if num != 0}
    if 0 in chapters:
        logger.debug("Skipping preamble (chapter 0)")

    logger.info("[DISPATCH] Routing %d chapters via LLM (model=%s)", len(numbered), router_model)

    tasks = [
        _ai_route_chapter(ch, ai_client, router_model, provider=provider)
        for ch in numbered.values()
    ]
    # Exceptions propagate — any failed chapter aborts the whole dispatch
    domains = await asyncio.gather(*tasks)

    for (num, ch), domain in zip(numbered.items(), domains):
        result[domain].append(ch)
        routing_map[num] = RoutingEntry(
            chapter_number=num,
            title=ch.title,
            domain=domain,
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
) -> str:
    """Use a fast LLM to classify a chapter.  Returns the domain name.

    Raises ValueError if the LLM returns an unrecognised domain.
    Any API error propagates so the caller fails fast.
    """
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

    if domain not in ALL_DOMAINS:
        raise ValueError(
            f"LLM returned unrecognised domain {domain!r} for"
            f" ch {chapter.number} ({chapter.title!r})"
        )

    logger.info("[DISPATCH] Ch %d (%s) -> %s", chapter.number, chapter.title, domain)
    return domain
