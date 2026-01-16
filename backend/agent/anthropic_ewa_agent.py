"""Agent responsible for producing a structured JSON summary for an SAP EWA report using Azure AI Foundry (Anthropic Claude)."""
from __future__ import annotations

import os
import json
import asyncio
import copy
import logging
from typing import Dict, Any
from jsonschema import validate, ValidationError
from utils.json_repair import JSONRepair

# Directory containing prompt templates
_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts")
_ANTHROPIC_PROMPT_PATH = os.path.join(_PROMPT_DIR, "ewa_summary_prompt_anthropic.md")

logger = logging.getLogger(__name__)

# Default prompt fallback
DEFAULT_PROMPT = """You are a highly experienced SAP Basis Architect. Analyze the SAP EarlyWatch Alert (EWA) report and produce a precise JSON output that strictly follows the provided schema."""


class AnthropicEWAAgent:
    """Agent that uses Azure AI Foundry (Anthropic Claude) to produce a validated JSON summary."""

    def __init__(
        self,
        client,  # AnthropicFoundry client
        model: str,
        summary_prompt: str | None = None,
        schema_path: str | None = None,
    ):
        self.client = client
        self.model = model

        # Load prompt
        if summary_prompt is not None:
            self.summary_prompt = summary_prompt
        elif os.path.exists(_ANTHROPIC_PROMPT_PATH):
            with open(_ANTHROPIC_PROMPT_PATH, "r", encoding="utf-8") as f:
                self.summary_prompt = f.read()
                logger.info("Loaded prompt from %s", _ANTHROPIC_PROMPT_PATH)
        else:
            self.summary_prompt = DEFAULT_PROMPT
            logger.warning("Using default prompt")

        # Load schema
        if schema_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(base_dir, "..", "schemas", "ewa_summary_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema: Dict[str, Any] = json.load(f)

        # Local JSON repair utility
        self.json_repair = JSONRepair()

    async def run(self, markdown: str, pdf_data: bytes = None) -> Dict[str, Any]:
        """Return a validated summary JSON object.
        
        Args:
            markdown: Markdown text of the document
            pdf_data: Unused, kept for API compatibility with EWAAgent
        """
        summary_json = await self._call_anthropic(markdown)
        
        if self._is_valid(summary_json):
            logger.info("Initial JSON valid; skipping repair")
            return summary_json

        # Try local repair
        logger.warning("Initial JSON invalid; invoking local JSON repair")
        summary_json = self._repair_local(summary_json)
        
        try:
            is_valid_after = self._is_valid(summary_json)
            logger.info("Local repair completed; valid=%s", is_valid_after)
        except Exception:
            logger.exception("Repair completed; validity check raised an exception")
        
        return summary_json

    async def _call_anthropic(self, markdown: str) -> Dict[str, Any]:
        """Call Azure AI Foundry (Anthropic Claude) Messages API."""
        
        # Build the user message with schema and document
        schema_str = json.dumps(self.schema, indent=2)
        user_content = f"""Analyze the following SAP EarlyWatch Alert document and produce a JSON output that strictly conforms to this schema:

```json
{schema_str}
```

Important:
- Output ONLY valid JSON, no markdown formatting or explanations.
- Include "Schema Version": "1.1" in your output.
- Use lowercase for severity, risk, and health rating values.
- Use ISO date format (YYYY-MM-DD) for dates.

---

EWA Document:

{markdown}
"""

        try:
            # Try streaming with stream=True parameter to avoid server-side timeout
            # This uses SSE (Server-Sent Events) which keeps the connection alive
            def _call_messages_streaming() -> tuple[str, int, int]:
                """Make streaming API call and return (text, input_tokens, output_tokens)."""
                collected_text = ""
                in_tokens = 0
                out_tokens = 0
                
                # Use stream=True parameter for SSE streaming
                stream = self.client.messages.create(
                    model=self.model,
                    max_tokens=32768,
                    system=self.summary_prompt,
                    messages=[
                        {"role": "user", "content": user_content}
                    ],
                    stream=True,
                )
                
                # Iterate over SSE events
                for event in stream:
                    # Handle different event types
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            # Extract text from delta
                            if hasattr(event, "delta") and hasattr(event.delta, "text"):
                                collected_text += event.delta.text
                        elif event.type == "message_delta":
                            # Extract usage from final message delta
                            if hasattr(event, "usage"):
                                out_tokens = getattr(event.usage, "output_tokens", 0)
                        elif event.type == "message_start":
                            # Extract input tokens from message start
                            if hasattr(event, "message") and hasattr(event.message, "usage"):
                                in_tokens = getattr(event.message.usage, "input_tokens", 0)
                
                return collected_text, in_tokens, out_tokens
            
            # Offload streaming call to a thread
            text, in_tokens, out_tokens = await asyncio.to_thread(_call_messages_streaming)
            logger.info(
                "Token usage: input_tokens=%s, output_tokens=%s",
                in_tokens,
                out_tokens,
            )

            if not text:
                logger.warning("No text content in response")
                return {"_parse_error": "No text content in response", "raw_arguments": ""}

            # Parse JSON from response
            return self._parse_json_from_text(text)

        except Exception as e:
            logger.exception("Error calling Anthropic API: %s", e)
            return {"_parse_error": str(e), "raw_arguments": ""}

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """Parse JSON from Claude's response text."""
        # Try direct parse first
        try:
            return json.loads(text)
        except Exception:
            pass

        # Try to extract JSON from markdown code blocks
        import re
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass

        # Try to find JSON object boundaries
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except Exception:
                # Try local repair
                try:
                    rr = self.json_repair.repair(candidate)
                    if rr.success and isinstance(rr.data, dict):
                        return rr.data
                except Exception:
                    pass

        # Return error sentinel
        return {"_parse_error": "Failed to parse JSON from response", "raw_arguments": text[:50000]}

    def _repair_local(self, previous_json: Dict[str, Any]) -> Dict[str, Any]:
        """Repair JSON locally without LLM calls."""
        try:
            if isinstance(previous_json, dict) and "raw_arguments" in previous_json:
                raw = previous_json.get("raw_arguments", "")
                rr = self.json_repair.repair(raw)
                if rr.success and isinstance(rr.data, dict):
                    return rr.data

            text = json.dumps(previous_json, ensure_ascii=False)
            rr = self.json_repair.repair(text)
            if rr.success and isinstance(rr.data, dict):
                return rr.data
        except Exception as e:
            logger.exception("Exception during local repair: %s", e)
        
        return previous_json

    def _is_valid(self, data: Dict[str, Any]) -> bool:
        """Validate data against the schema."""
        try:
            validate(instance=data, schema=self.schema)
            return True
        except ValidationError:
            return False
