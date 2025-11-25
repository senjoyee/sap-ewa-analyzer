"""Phase 3 Agent: Executive synthesis and recommendations using Azure OpenAI Responses API."""
from __future__ import annotations

import os
import json
import asyncio
import copy
from typing import Dict, Any

from openai import AzureOpenAI
from jsonschema import validate, ValidationError


class StrategyAgent:
    """Phase 3: Synthesize findings into executive summary and actionable recommendations."""

    def __init__(self, client: AzureOpenAI, model: str):
        self.client = client
        self.model = model

        # Load prompt
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "strategy_prompt.md"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt = f.read()

        # Load schema
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "schemas", "strategy_schema.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    async def run(self, phase1_data: Dict[str, Any], phase2_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate strategy from Phase 1+2 data. Does NOT need original document."""
        print(f"[StrategyAgent] Starting synthesis with model: {self.model}")

        phase1_context = json.dumps(phase1_data, indent=2)
        phase2_context = json.dumps(phase2_data, indent=2)

        user_content = [
            {
                "type": "input_text",
                "text": (
                    f"{self.prompt}\n\n"
                    f"---\n\n"
                    f"## Phase 1: Extracted Metadata\n```json\n{phase1_context}\n```\n\n"
                    f"---\n\n"
                    f"## Phase 2: Analysis Results\n```json\n{phase2_context}\n```"
                ),
            }
        ]

        strict_schema = self._make_strict_schema(self.schema)

        text_format = {
            "format": {
                "type": "json_schema",
                "name": "generate_ewa_strategy",
                "schema": strict_schema,
                "strict": True,
            }
        }

        # Medium reasoning effort - reformatting structured data
        response = await asyncio.to_thread(
            lambda: self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": user_content}],
                text=text_format,
                max_output_tokens=12288,
                reasoning={"effort": "medium"},
            )
        )

        self._log_usage(response)

        result = self._parse_response(response)
        self._validate(result, phase2_data)

        rec_count = len(result.get("Recommendations", []))
        print(f"[StrategyAgent] Synthesis complete: {rec_count} recommendations")
        return result

    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse response from Responses API."""
        parsed = getattr(response, "output_parsed", None)
        if parsed and isinstance(parsed, dict):
            return parsed

        text = getattr(response, "output_text", None)
        if text:
            return json.loads(text)

        raise RuntimeError("No output from StrategyAgent")

    def _validate(self, data: Dict[str, Any], phase2_data: Dict[str, Any]) -> None:
        """Validate against schema and check 1:1 linkage to findings."""
        try:
            validate(instance=data, schema=self.schema)
        except ValidationError as e:
            print(f"[StrategyAgent] Validation warning: {e.message}")

        # Check 1:1 mapping
        finding_ids = {f.get("Issue ID") for f in phase2_data.get("Key Findings", [])}
        rec_links = {r.get("Linked issue ID") for r in data.get("Recommendations", [])}
        
        missing = finding_ids - rec_links
        if missing:
            print(f"[StrategyAgent] Warning: Findings without recommendations: {missing}")

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
                print(f"[StrategyAgent] Tokens: input={in_tok}, output={out_tok}")
        except Exception:
            pass
