"""Domain specialist agents for the EWA V2 agentic pipeline.

Each specialist receives only its domain's chapters and extracts RED/YELLOW
findings using the Azure OpenAI Responses API with structured outputs.
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
from utils.ewa_slicer import ChapterData

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent
_PROMPTS_DIR = _BASE_DIR / "prompts"
_SCHEMAS_DIR = _BASE_DIR / "schemas"
_DOMAIN_RESULT_SCHEMA_PATH = _SCHEMAS_DIR / "domain_result_schema.json"
_BUSINESS_SCHEMA_PATH = _SCHEMAS_DIR / "business_result_schema.json"
_PERFORMANCE_SCHEMA_PATH = _SCHEMAS_DIR / "performance_result_schema.json"

# Finding ID prefixes per domain
DOMAIN_PREFIXES: dict[str, str] = {
    "security": "SEC",
    "database": "DB",
    "performance": "PERF",
    "basis": "BAS",
    "business": "BIZ",
    "lifecycle": "LCM",
}

# Prompt file names per domain
DOMAIN_PROMPT_FILES: dict[str, str] = {
    "security": "specialist_security_prompt.md",
    "database": "specialist_database_prompt.md",
    "performance": "specialist_performance_prompt.md",
    "basis": "specialist_basis_prompt.md",
    "business": "specialist_business_prompt.md",
    "lifecycle": "specialist_lifecycle_prompt.md",
}


@dataclass
class DomainResult:
    """Structured output from a specialist agent."""
    domain: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    abstentions: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    applicable: bool = True  # False for business domain on non-ECC/S4 systems

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "findings": self.findings,
            "parameters": self.parameters,
            "abstentions": self.abstentions,
            "applicable": self.applicable,
        }


class SpecialistAgent:
    """Base class for domain specialist agents.

    Uses Azure OpenAI Responses API with structured outputs (json_schema).
    Each subclass just specifies the domain and prompt file.
    """

    def __init__(
        self,
        client: Any,
        model: str,
        domain: str,
        prompt_path: Path | None = None,
        schema_path: Path | None = None,
        reasoning_effort: str = "none",
        max_output_tokens: int = 16384,
        provider: str = "openai",
    ):
        self.client = client
        self.model = model
        self.domain = domain
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens
        self.provider = provider.lower()
        self.last_usage: dict[str, Any] = {}
        self.json_repair = JSONRepair()

        # Load prompt
        if prompt_path is None:
            prompt_file = DOMAIN_PROMPT_FILES.get(domain)
            if not prompt_file:
                raise ValueError(f"No prompt file configured for domain: {domain}")
            prompt_path = _PROMPTS_DIR / prompt_file

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        self.prompt = prompt_path.read_text(encoding="utf-8")

        # Load schema
        if schema_path is None:
            schema_path = _DOMAIN_RESULT_SCHEMA_PATH
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema: dict[str, Any] = json.load(f)

        self.strict_schema = self._make_strict_schema(self.schema)

    async def run(self, chapters: list[ChapterData]) -> DomainResult:
        """Analyze assigned chapters and return structured domain result."""
        if not chapters:
            logger.info("No chapters assigned to %s specialist, returning empty result", self.domain)
            return DomainResult(domain=self.domain)

        # Build the document context from assigned chapters
        context = self._build_context(chapters)
        logger.info(
            "%s specialist: %d chapters, %d chars of context",
            self.domain, len(chapters), len(context),
        )

        # Call LLM
        raw_json = await self._call_llm(context)

        # Validate and repair
        if not self._is_valid(raw_json):
            logger.warning("%s specialist: initial output invalid, attempting repair", self.domain)
            raw_json = self._repair(raw_json)

        # Normalize finding IDs
        raw_json = self._normalize_finding_ids(raw_json)

        return DomainResult(
            domain=raw_json.get("domain", self.domain),
            findings=raw_json.get("findings", []),
            parameters=raw_json.get("parameters", []),
            abstentions=raw_json.get("abstentions", []),
            usage=self.last_usage,
            applicable=raw_json.get("applicable", True),
        )

    def _build_context(self, chapters: list[ChapterData]) -> str:
        """Concatenate chapter contents with clear separators."""
        parts: list[str] = []
        for ch in chapters:
            parts.append(f"--- Chapter {ch.number}: {ch.title} ---")
            parts.append(ch.raw_content)
            parts.append("")  # blank line separator
        return "\n".join(parts)

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
            "Do not include any text outside of the JSON. Use double-quoted keys and strings, "
            "no trailing commas, and no comments."
        )

        user_content = [
            {"type": "input_text", "text": context},
            {"type": "input_text", "text": instruction_text},
        ]

        text_format = {
            "format": {
                "type": "json_schema",
                "name": f"extract_{self.domain}_findings",
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

            # Try structured parsed output first
            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                    return parsed[0]

            # Fall back to output_text
            text = getattr(response, "output_text", None)
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    rr = self.json_repair.repair(text)
                    if rr.success and isinstance(rr.data, dict):
                        return rr.data
                    return {"domain": self.domain, "findings": [], "parameters": [], "abstentions": [],
                            "_parse_error": True, "raw_arguments": text[:20000]}

            logger.warning("%s specialist: no output from LLM", self.domain)
            return {"domain": self.domain, "findings": [], "parameters": [], "abstentions": []}

        except Exception:
            logger.exception("%s specialist: LLM call failed", self.domain)
            return {"domain": self.domain, "findings": [], "parameters": [], "abstentions": []}

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
            "Do not include any text outside of the JSON. Use double-quoted keys and strings, "
            "no trailing commas, and no comments."
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
                logger.warning("%s specialist: Anthropic structured output returned no text, falling back to streaming", self.domain)
            except Exception as e:
                logger.warning("%s specialist: Anthropic structured output failed, falling back to streaming: %s", self.domain, e)

            # Streaming fallback
            text, in_tok, out_tok, cached_tok = await asyncio.to_thread(
                self._call_anthropic_streaming, system_blocks, messages_content
            )
            self.last_usage = {
                "model": self.model,
                "domain": self.domain,
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
            return {"domain": self.domain, "findings": [], "parameters": [], "abstentions": []}

        except Exception:
            logger.exception("%s specialist: Anthropic call failed", self.domain)
            return {"domain": self.domain, "findings": [], "parameters": [], "abstentions": []}

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
            "domain": self.domain,
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
        """Extract token usage from response."""
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
            "domain": self.domain,
            "input_tokens": (usage or {}).get("input_tokens"),
            "cached_input_tokens": (input_details if isinstance(input_details, dict) else {}).get("cached_tokens", 0) or 0,
            "output_tokens": (usage or {}).get("output_tokens"),
            "reasoning_tokens": (output_details if isinstance(output_details, dict) else {}).get("reasoning_tokens", 0) or 0,
            "total_tokens": (usage or {}).get("total_tokens"),
        }

    def _normalize_finding_ids(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure all finding IDs follow the domain prefix convention."""
        prefix = DOMAIN_PREFIXES.get(self.domain, self.domain.upper()[:3])
        for i, finding in enumerate(data.get("findings", []), start=1):
            fid = finding.get("finding_id", "")
            if not fid or not fid.startswith(prefix):
                finding["finding_id"] = f"{prefix}-{i:02d}"
        return data

    def _make_strict_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Prepare schema for OpenAI strict mode.

        - Strips meta-keywords ($schema, $id) not accepted by the Responses API.
        - Ensures additionalProperties: false on every object node.
        """
        # Strip top-level JSON Schema meta-keywords that OpenAI does not accept
        _STRIP_KEYS = {"$schema", "$id"}

        def visit(node: Any) -> Any:
            if isinstance(node, dict):
                # Remove unsupported meta-keywords at any level
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

    def _is_valid(self, data: dict[str, Any]) -> bool:
        try:
            validate(instance=data, schema=self.schema)
            return True
        except (ValidationError, Exception):
            return False

    def _repair(self, data: dict[str, Any]) -> dict[str, Any]:
        """Try to repair malformed JSON output."""
        try:
            if isinstance(data, dict) and "raw_arguments" in data:
                rr = self.json_repair.repair(data["raw_arguments"])
                if rr.success and isinstance(rr.data, dict):
                    return rr.data
            text = json.dumps(data, ensure_ascii=False)
            rr = self.json_repair.repair(text)
            if rr.success and isinstance(rr.data, dict):
                return rr.data
        except Exception:
            logger.exception("%s specialist: repair failed", self.domain)
        return data


# ---------------------------------------------------------------------------
# Concrete specialist subclasses (one-liners)
# ---------------------------------------------------------------------------

class SecuritySpecialist(SpecialistAgent):
    def __init__(self, client: Any, model: str, **kwargs):
        super().__init__(client, model, domain="security", **kwargs)


class DatabaseSpecialist(SpecialistAgent):
    def __init__(self, client: Any, model: str, **kwargs):
        super().__init__(client, model, domain="database", **kwargs)


class PerformanceSpecialist(SpecialistAgent):
    def __init__(self, client: Any, model: str, **kwargs):
        super().__init__(client, model, domain="performance", schema_path=_PERFORMANCE_SCHEMA_PATH, **kwargs)


class BasisSpecialist(SpecialistAgent):
    def __init__(self, client: Any, model: str, **kwargs):
        super().__init__(client, model, domain="basis", **kwargs)


class BusinessSpecialist(SpecialistAgent):
    def __init__(self, client: Any, model: str, **kwargs):
        super().__init__(client, model, domain="business", schema_path=_BUSINESS_SCHEMA_PATH, **kwargs)


class LifecycleSpecialist(SpecialistAgent):
    def __init__(self, client: Any, model: str, **kwargs):
        super().__init__(client, model, domain="lifecycle", **kwargs)


# ---------------------------------------------------------------------------
# Parallel runner
# ---------------------------------------------------------------------------

SPECIALIST_CLASSES: dict[str, type[SpecialistAgent]] = {
    "security": SecuritySpecialist,
    "database": DatabaseSpecialist,
    "performance": PerformanceSpecialist,
    "basis": BasisSpecialist,
    "business": BusinessSpecialist,
    "lifecycle": LifecycleSpecialist,
}


async def run_all_specialists(
    domain_chapters: dict[str, list[ChapterData]],
    client: Any,
    model: str,
    reasoning_effort: str = "none",
    max_output_tokens: int = 16384,
    provider: str = "openai",
) -> list[DomainResult]:
    """Run all 6 specialist agents in parallel via asyncio.gather.

    Returns a list of DomainResult objects (one per domain).
    Domains with no chapters get an empty DomainResult without an LLM call.
    """
    tasks = []
    for domain, cls in SPECIALIST_CLASSES.items():
        chapters = domain_chapters.get(domain, [])
        agent = cls(client, model, reasoning_effort=reasoning_effort, max_output_tokens=max_output_tokens, provider=provider)
        tasks.append(agent.run(chapters))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    domain_results: list[DomainResult] = []
    for domain, result in zip(SPECIALIST_CLASSES.keys(), results):
        if isinstance(result, Exception):
            logger.error("%s specialist raised an exception: %s", domain, result, exc_info=result)
            domain_results.append(DomainResult(domain=domain))
        else:
            domain_results.append(result)

    return domain_results
