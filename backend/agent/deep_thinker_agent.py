"""Deep Thinker agent for cross-domain implicit risk analysis.

Consumes all 6 specialist DomainResult outputs and identifies risks that
are not flagged RED/YELLOW by SAP but are logically dangerous.
"""
from __future__ import annotations

import os
import json
import copy
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict
from dataclasses import dataclass, field

from jsonschema import validate, ValidationError
from utils.json_repair import JSONRepair
from agent.specialist_agents import DomainResult

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent
_PROMPT_PATH = _BASE_DIR / "prompts" / "deep_thinker_prompt.md"
_SCHEMA_PATH = _BASE_DIR / "schemas" / "deep_thinker_schema.json"


@dataclass
class SupplementalFinding:
    """A derived recommendation identified by the Deep Thinker."""
    finding_id: str
    title: str
    domain: str
    finding: str
    rationale: str
    recommendation: str
    source: str  # always "AI Deep Analysis"

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "domain": self.domain,
            "finding": self.finding,
            "rationale": self.rationale,
            "recommendation": self.recommendation,
            "source": self.source,
        }


class DeepThinkerAgent:
    """Cross-domain analysis agent that identifies implicit risks.

    Runs as a single consolidated pass over all specialist outputs.
    Uses Azure OpenAI Responses API with structured outputs.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        prompt_path: Path | None = None,
        schema_path: Path | None = None,
        reasoning_effort: str = "medium",
        max_output_tokens: int = 16384,
        provider: str = "openai",
    ):
        self.client = client
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens
        self.provider = provider.lower()
        self.last_usage: dict[str, Any] = {}
        self.json_repair = JSONRepair()

        # Load prompt
        pp = prompt_path or _PROMPT_PATH
        if not pp.exists():
            raise FileNotFoundError(f"Deep thinker prompt not found: {pp}")
        self.prompt = pp.read_text(encoding="utf-8")

        # Load schema
        sp = schema_path or _SCHEMA_PATH
        with open(sp, "r", encoding="utf-8") as f:
            self.schema: dict[str, Any] = json.load(f)
        self.strict_schema = self._make_strict_schema(self.schema)

    async def run(self, domain_results: list[DomainResult]) -> list[SupplementalFinding]:
        """Analyze all specialist outputs and return supplemental findings."""
        # Serialize all domain results for the LLM
        payload = [dr.to_dict() for dr in domain_results]
        context = json.dumps(payload, indent=2, ensure_ascii=False)

        logger.info("Deep Thinker: analyzing %d domain results (%d chars)", len(domain_results), len(context))

        raw_json = await self._call_llm(context)
        findings_list = raw_json.get("supplemental_findings", [])

        # Normalize IDs
        for i, f in enumerate(findings_list, start=1):
            fid = f.get("finding_id", "")
            if not fid or not fid.startswith("DT-"):
                f["finding_id"] = f"DT-{i:02d}"
            # Enforce constant field
            f["source"] = "AI Deep Analysis"

        results = []
        for f in findings_list:
            results.append(SupplementalFinding(
                finding_id=f.get("finding_id", ""),
                title=f.get("title", ""),
                domain=f.get("domain", ""),
                finding=f.get("finding", ""),
                rationale=f.get("rationale", ""),
                recommendation=f.get("recommendation", ""),
                source=f.get("source", "AI Deep Analysis"),
            ))

        logger.info("Deep Thinker: produced %d supplemental findings", len(results))
        return results

    async def _call_llm(self, context: str) -> dict[str, Any]:
        """Dispatch to the appropriate LLM backend."""
        if self.provider == "anthropic":
            return await self._call_llm_anthropic(context)
        return await self._call_llm_openai(context)

    async def _call_llm_openai(self, context: str) -> dict[str, Any]:
        """Call Azure OpenAI Responses API with structured output."""
        instruction_text = (
            f"{self.prompt}\n\n"
            "Return ONLY a valid JSON object that strictly conforms to the provided JSON schema. "
            "Do not include any text outside of the JSON."
        )

        user_content = [
            {"type": "input_text", "text": context},
            {"type": "input_text", "text": instruction_text},
        ]

        text_format = {
            "format": {
                "type": "json_schema",
                "name": "deep_thinker_analysis",
                "schema": self.strict_schema,
                "strict": True,
            },
        }

        try:
            response = await asyncio.to_thread(
                lambda: self.client.responses.create(
                    model=self.model,
                    input=[{"role": "user", "content": user_content}],
                    text=text_format,
                    reasoning={"effort": self.reasoning_effort},
                    max_output_tokens=self.max_output_tokens,
                )
            )
            self.last_usage = self._extract_usage(response)

            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                    return parsed[0]

            text = getattr(response, "output_text", None)
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    rr = self.json_repair.repair(text)
                    if rr.success and isinstance(rr.data, dict):
                        return rr.data

            logger.warning("Deep Thinker: no output from LLM")
            return {"supplemental_findings": []}

        except Exception:
            logger.exception("Deep Thinker: LLM call failed")
            return {"supplemental_findings": []}

    async def _call_llm_anthropic(self, context: str) -> dict[str, Any]:
        """Call Anthropic Messages API with structured output."""
        system_blocks = [
            {
                "type": "text",
                "text": self.prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        instruction_text = (
            "Return ONLY a valid JSON object that strictly conforms to the provided JSON schema. "
            "Do not include any text outside of the JSON."
        )
        messages_content = [
            {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": instruction_text},
        ]

        try:
            def _call_structured():
                return self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_output_tokens,
                    system=system_blocks,
                    messages=[{"role": "user", "content": messages_content}],
                    output_config={
                        "format": {
                            "type": "json_schema",
                            "schema": self.strict_schema,
                        }
                    },
                    stream=False,
                )

            try:
                response = await asyncio.to_thread(_call_structured)
                self.last_usage = self._extract_usage_anthropic(response)
                text = self._extract_text_from_anthropic(response)
                if text:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        rr = self.json_repair.repair(text)
                        if rr.success and isinstance(rr.data, dict):
                            return rr.data
                logger.warning("Deep Thinker: Anthropic structured output returned no text, falling back to streaming")
            except Exception as e:
                logger.warning("Deep Thinker: Anthropic structured output failed, falling back to streaming: %s", e)

            # Streaming fallback
            text, in_tok, out_tok, cached_tok = await asyncio.to_thread(
                self._call_anthropic_streaming, system_blocks, messages_content
            )
            self.last_usage = {
                "model": self.model,
                "role": "deep_thinker",
                "input_tokens": in_tok + cached_tok,
                "cached_input_tokens": cached_tok,
                "output_tokens": out_tok,
                "reasoning_tokens": 0,
                "total_tokens": in_tok + cached_tok + out_tok,
            }
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    rr = self.json_repair.repair(text)
                    if rr.success and isinstance(rr.data, dict):
                        return rr.data
            return {"supplemental_findings": []}

        except Exception:
            logger.exception("Deep Thinker: Anthropic call failed")
            return {"supplemental_findings": []}

    def _extract_text_from_anthropic(self, response: Any) -> str:
        """Extract text content from a non-streaming Anthropic response."""
        parts: list[str] = []
        for block in (getattr(response, "content", None) or []):
            if getattr(block, "type", None) == "text":
                t = getattr(block, "text", None)
                if t:
                    parts.append(t)
        return "".join(parts)

    def _extract_usage_anthropic(self, response: Any) -> dict[str, Any]:
        """Extract token usage from a non-streaming Anthropic response."""
        usage = getattr(response, "usage", None)
        in_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        out_tokens = getattr(usage, "output_tokens", 0) if usage else 0
        cached_tokens = getattr(usage, "cache_read_tokens", 0) if usage else 0
        return {
            "model": self.model,
            "role": "deep_thinker",
            "input_tokens": in_tokens + (cached_tokens or 0),
            "cached_input_tokens": cached_tokens or 0,
            "output_tokens": out_tokens,
            "reasoning_tokens": 0,
            "total_tokens": in_tokens + (cached_tokens or 0) + out_tokens,
        }

    def _call_anthropic_streaming(
        self, system_blocks: list, messages_content: list
    ) -> tuple[str, int, int, int]:
        """Streaming fallback for Anthropic. Returns (text, in_tokens, out_tokens, cached_tokens)."""
        collected_text = ""
        in_tokens = 0
        out_tokens = 0
        cached_tokens = 0

        stream = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_output_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": messages_content}],
            stream=True,
        )
        for event in stream:
            if not hasattr(event, "type"):
                continue
            if event.type == "content_block_delta":
                if hasattr(event, "delta") and hasattr(event.delta, "text"):
                    collected_text += event.delta.text
            elif event.type == "message_delta":
                if hasattr(event, "usage"):
                    out_tokens = getattr(event.usage, "output_tokens", 0)
            elif event.type == "message_start":
                if hasattr(event, "message") and hasattr(event.message, "usage"):
                    in_tokens = getattr(event.message.usage, "input_tokens", 0)
                    cached_tokens = getattr(event.message.usage, "cache_read_tokens", 0) or 0
        return collected_text, in_tokens, out_tokens, cached_tokens

    def _extract_usage(self, response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        elif usage is not None and not isinstance(usage, dict):
            usage = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }

        input_details = (usage or {}).get("input_tokens_details") or {}
        output_details = (usage or {}).get("output_tokens_details") or {}
        if hasattr(input_details, "model_dump"):
            input_details = input_details.model_dump()
        if hasattr(output_details, "model_dump"):
            output_details = output_details.model_dump()

        return {
            "model": self.model,
            "role": "deep_thinker",
            "input_tokens": (usage or {}).get("input_tokens"),
            "cached_input_tokens": (input_details if isinstance(input_details, dict) else {}).get("cached_tokens", 0) or 0,
            "output_tokens": (usage or {}).get("output_tokens"),
            "reasoning_tokens": (output_details if isinstance(output_details, dict) else {}).get("reasoning_tokens", 0) or 0,
            "total_tokens": (usage or {}).get("total_tokens"),
        }

    def _make_strict_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Prepare schema for OpenAI strict mode.

        - Strips meta-keywords ($schema, $id) not accepted by the Responses API.
        - Ensures additionalProperties: false on every object node.
        """
        _STRIP_KEYS = {"$schema", "$id"}

        def visit(node: Any) -> Any:
            if isinstance(node, dict):
                for k in _STRIP_KEYS:
                    node.pop(k, None)
                if node.get("type") == "object":
                    node["additionalProperties"] = False
                    props = node.get("properties")
                    if isinstance(props, dict):
                        for k, v in props.items():
                            props[k] = visit(v)
                items = node.get("items")
                if isinstance(items, dict):
                    node["items"] = visit(items)
                elif isinstance(items, list):
                    node["items"] = [visit(it) for it in items]
                for key in ("allOf", "anyOf", "oneOf"):
                    seq = node.get(key)
                    if isinstance(seq, list):
                        node[key] = [visit(s) for s in seq]
                return node
            elif isinstance(node, list):
                return [visit(n) for n in node]
            return node

        return visit(copy.deepcopy(schema))
