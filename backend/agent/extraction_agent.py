"""Phase 1 Agent: Pure data extraction from SAP EWA report using Azure OpenAI Responses API."""
from __future__ import annotations

import os
import json
import asyncio
import copy
from typing import Dict, Any

from openai import AzureOpenAI
from jsonschema import validate, ValidationError


class ExtractionAgent:
    """Phase 1: Extract raw data (metadata, chapters, capacity) without analysis."""

    def __init__(self, client: AzureOpenAI, model: str):
        self.client = client
        self.model = model

        # Load prompt
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "extraction_prompt.md"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt = f.read()

        # Load schema
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "schemas", "extraction_schema.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    async def run(self, markdown_content: str) -> Dict[str, Any]:
        """Extract data from markdown content. Returns validated JSON."""
        print(f"[ExtractionAgent] Starting extraction with model: {self.model}")

        user_content = [
            {"type": "input_text", "text": f"{self.prompt}\n\n---\n\n{markdown_content}"}
        ]

        strict_schema = self._make_strict_schema(self.schema)

        text_format = {
            "format": {
                "type": "json_schema",
                "name": "extract_ewa_data",
                "schema": strict_schema,
                "strict": True,
            }
        }

        response = await asyncio.to_thread(
            lambda: self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": user_content}],
                text=text_format,
                max_output_tokens=4096,
                reasoning={"effort": "low"},
            )
        )

        self._log_usage(response)

        result = self._parse_response(response)
        self._validate(result)
        
        print(f"[ExtractionAgent] Extraction complete: SID={result.get('System Metadata', {}).get('System ID', 'Unknown')}")
        return result

    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse response from Responses API."""
        parsed = getattr(response, "output_parsed", None)
        if parsed and isinstance(parsed, dict):
            return parsed

        text = getattr(response, "output_text", None)
        if text:
            return json.loads(text)

        raise RuntimeError("No output from ExtractionAgent")

    def _validate(self, data: Dict[str, Any]) -> None:
        """Validate against schema."""
        try:
            validate(instance=data, schema=self.schema)
        except ValidationError as e:
            print(f"[ExtractionAgent] Validation warning: {e.message}")
            # Don't raise - let downstream handle

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
                print(f"[ExtractionAgent] Tokens: input={in_tok}, output={out_tok}")
        except Exception:
            pass
