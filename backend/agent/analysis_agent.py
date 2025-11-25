"""Phase 2 Agent: Deep analytical assessment using Azure OpenAI Responses API."""
from __future__ import annotations

import os
import json
import asyncio
import copy
from typing import Dict, Any

from openai import AzureOpenAI
from jsonschema import validate, ValidationError
from json_repair import repair_json


class AnalysisAgent:
    """Phase 2: Deep analysis with high reasoning effort - the core analytical work."""

    def __init__(self, client: AzureOpenAI, model: str):
        self.client = client
        self.model = model

        # Load prompt
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "analysis_prompt.md"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt = f.read()

        # Load schema
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "schemas", "analysis_schema.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    async def run(self, markdown_content: str, phase1_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze document with Phase 1 context. Returns validated JSON."""
        print(f"[AnalysisAgent] Starting analysis with model: {self.model}")

        # Build context from Phase 1
        phase1_context = json.dumps(phase1_data, indent=2)

        user_content = [
            {
                "type": "input_text",
                "text": (
                    f"{self.prompt}\n\n"
                    f"---\n\n"
                    f"## Phase 1 Extracted Data\n```json\n{phase1_context}\n```\n\n"
                    f"---\n\n"
                    f"## EWA Report Content\n{markdown_content}"
                ),
            }
        ]

        strict_schema = self._make_strict_schema(self.schema)

        text_format = {
            "format": {
                "type": "json_schema",
                "name": "analyze_ewa_report",
                "schema": strict_schema,
                "strict": True,
            }
        }

        # HIGH reasoning effort - this is where quality matters
        response = await asyncio.to_thread(
            lambda: self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": user_content}],
                text=text_format,
                max_output_tokens=16384,
                reasoning={"effort": "high"},
            )
        )

        self._log_usage(response)

        result = self._parse_response(response)
        self._validate(result)

        findings_count = len(result.get("Key Findings", []))
        risk = result.get("Overall Risk", "unknown")
        print(f"[AnalysisAgent] Analysis complete: {findings_count} findings, risk={risk}")
        return result

    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse response from Responses API with JSON repair fallback."""
        parsed = getattr(response, "output_parsed", None)
        if parsed and isinstance(parsed, dict):
            return parsed

        text = getattr(response, "output_text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                print(f"[AnalysisAgent] JSON parse failed, attempting repair: {e}")
                repaired = repair_json(text, return_objects=True)
                if isinstance(repaired, dict):
                    print("[AnalysisAgent] JSON repair successful")
                    return repaired
                raise RuntimeError(f"JSON repair failed: got {type(repaired)}")

        raise RuntimeError("No output from AnalysisAgent")

    def _validate(self, data: Dict[str, Any]) -> None:
        """Validate against schema."""
        try:
            validate(instance=data, schema=self.schema)
        except ValidationError as e:
            print(f"[AnalysisAgent] Validation warning: {e.message}")

    def _make_strict_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Add additionalProperties: false to all objects for strict mode."""
        def visit(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    node["additionalProperties"] = False
                    if "properties" in node:
                        for v in node["properties"].values():
                            visit(v)
                if "items" in node:
                    visit(node["items"])
            return node
        return visit(copy.deepcopy(schema))

    def _log_usage(self, response) -> None:
        """Log token usage."""
        try:
            usage = getattr(response, "usage", None)
            if usage:
                in_tok = getattr(usage, "input_tokens", None)
                out_tok = getattr(usage, "output_tokens", None)
                reason_tok = getattr(usage, "reasoning_tokens", None) or getattr(
                    getattr(usage, "output_tokens_details", None), "reasoning_tokens", None
                )
                print(f"[AnalysisAgent] Tokens: input={in_tok}, output={out_tok}, reasoning={reason_tok}")
        except Exception:
            pass
