"""
Parameter Extraction Agent using GPT-5-mini for extracting SAP parameter recommendations.
Runs as a post-processing step after main EWA analysis to extract parameter changes from markdown.
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from core.runtime_config import PARAM_MAX_OUTPUT_TOKENS, PARAM_REASONING_EFFORT, ANTHROPIC_THINKING_BUDGET_TOKENS
from utils.json_repair import JSONRepair

# Action status values for parameter classification
ACTION_STATUS_CHANGE_REQUIRED = "Change Required"
ACTION_STATUS_VERIFY = "Verify"
ACTION_STATUS_NO_ACTION = "No Action"
ACTION_STATUS_MONITOR = "Monitor"

# Priority levels
PRIORITY_HIGH = "High"
PRIORITY_MEDIUM = "Medium"
PRIORITY_LOW = "Low"

# Schema for parameter extraction
# Schema file path
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schemas", "parameter_extraction_schema.json")

# Prompt file path
PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts", "parameter_extraction_prompt.md")

logger = logging.getLogger(__name__)


class ParameterExtractionAgent:
    """Agent for extracting parameter recommendations using GPT-5."""
    
    def __init__(self, client, model: str = None, provider: str = "openai", reasoning_effort: str | None = None, thinking_budget: int | None = None):
        """
        Initialize the parameter extraction agent.
        
        Args:
            client: Azure OpenAI client instance
            model: Model deployment name (defaults to AZURE_OPENAI_PARAM_MODEL or gpt-5.1)
        """
        self.client = client
        self.last_usage: Dict[str, Any] = {}
        self.provider = (provider or "openai").lower()
        self.model = model or (
            os.getenv("ANTHROPIC_SUMMARY_MODEL", "claude-sonnet-4-5")
            if self.provider == "anthropic"
            else os.getenv("AZURE_OPENAI_PARAM_MODEL", "gpt-5.1")
        )
        self.reasoning_effort = reasoning_effort or PARAM_REASONING_EFFORT
        self.thinking_budget = thinking_budget if thinking_budget is not None else ANTHROPIC_THINKING_BUDGET_TOKENS
        
        # Load schema
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.schema = json.load(f)
            
        # Load prompt
        if os.path.exists(PROMPT_PATH):
            with open(PROMPT_PATH, "r", encoding="utf-8") as f:
                self.prompt = f.read()
        else:
             # Fallback if file not found (though it should be there)
            self.prompt = "Error: Parameter extraction prompt file not found."
            logger.warning("Prompt file not found at %s", PROMPT_PATH)
            
        self.json_repair = JSONRepair()

    
    async def extract(self, markdown_content: str) -> Dict[str, Any]:
        """
        Extract parameter recommendations from markdown content.
        
        Args:
            markdown_content: The EWA report markdown content
            
        Returns:
            Dictionary with 'parameters' list, 'extraction_notes', and 'summary'
        """
        if not markdown_content or not markdown_content.strip():
            return {"parameters": [], "extraction_notes": "Empty input content", "summary": self.get_summary_stats([])}
        
        try:
            result = await (
                self._call_anthropic_api(markdown_content)
                if self.provider == "anthropic"
                else self._call_api(markdown_content)
            )
            
            # Validate result structure
            if not isinstance(result, dict):
                return {"parameters": [], "extraction_notes": "Invalid response format", "summary": self.get_summary_stats([])}
            
            parameters = result.get("parameters", [])
            if not isinstance(parameters, list):
                parameters = []
            
            # Filter out invalid entries and apply post-processing
            valid_params = []
            for param in parameters:
                if isinstance(param, dict) and param.get("parameter_name"):
                    recommended_value = str(param.get("recommended_value", ""))
                    action_status = str(param.get("action_status", ""))
                    priority = str(param.get("priority", ""))
                    
                    # Auto-classify if action_status is missing or recommended_value is empty
                    if not recommended_value.strip():
                        action_status = ACTION_STATUS_NO_ACTION
                        priority = PRIORITY_LOW
                    elif not action_status:
                        # Default to Change Required if has recommendation but no status
                        action_status = ACTION_STATUS_CHANGE_REQUIRED
                        priority = priority or PRIORITY_MEDIUM
                    
                    # Ensure valid enum values
                    if action_status not in [ACTION_STATUS_CHANGE_REQUIRED, ACTION_STATUS_VERIFY, 
                                              ACTION_STATUS_NO_ACTION, ACTION_STATUS_MONITOR]:
                        action_status = ACTION_STATUS_NO_ACTION
                    
                    if priority not in [PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]:
                        priority = PRIORITY_LOW
                    
                    valid_params.append({
                        "parameter_name": str(param.get("parameter_name", "")),
                        "area": str(param.get("area", "General")),
                        "current_value": str(param.get("current_value", "")),
                        "recommended_value": recommended_value,
                        "action_status": action_status,
                        "priority": priority,
                        "description": str(param.get("description", "")),
                        "source_section": str(param.get("source_section", "")),
                    })
            
            summary = self.get_summary_stats(valid_params)
            logger.info("Extracted %s valid parameters", len(valid_params))
            logger.debug("Summary: %s", summary)
            
            return {
                "parameters": valid_params,
                "extraction_notes": result.get("extraction_notes", ""),
                "summary": summary
            }
            
        except Exception as e:
            logger.exception("Error during extraction: %s", e)
            return {"parameters": [], "extraction_notes": f"Extraction error: {str(e)}", "summary": self.get_summary_stats([])}

    async def _call_anthropic_api(self, markdown_content: str) -> Dict[str, Any]:
        strict_schema = self._make_strict_schema(self.schema)
        user_content = markdown_content

        def extract_usage(response: Any) -> Dict[str, Any]:
            usage = getattr(response, "usage", None)
            in_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
            cached_tokens = getattr(usage, "cache_read_tokens", 0) if usage else 0
            thinking_tokens = getattr(usage, "thinking_tokens", 0) if usage else 0
            total_input = in_tokens + (cached_tokens or 0)
            return {
                "model": self.model,
                "reasoning_effort": self.reasoning_effort,
                "input_tokens": total_input,
                "cached_input_tokens": cached_tokens or 0,
                "output_tokens": output_tokens,
                "reasoning_tokens": thinking_tokens or 0,
                "total_tokens": total_input + output_tokens,
            }

        def call_messages_structured() -> Any:
            # Construct message content for Anthropic Caching:
            system_blocks = [
                {
                    "type": "text",
                    "text": self.prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
            
            messages_content = [
                {
                    "type": "text",
                    "text": user_content,
                    "cache_control": {"type": "ephemeral"}
                }
            ]

            kwargs = {
                "model": self.model,
                "max_tokens": PARAM_MAX_OUTPUT_TOKENS,
                "system": system_blocks,
                "messages": [
                    {"role": "user", "content": messages_content}
                ],
                "output_config": {
                    "format": {
                        "type": "json_schema",
                        "name": "extract_parameters",
                        "schema": strict_schema,
                    }
                },
                "temperature": 0.0,
                "stream": False,
            }

            # NOTE: Thinking mode is intentionally NOT used with structured output.
            # Per Anthropic docs, extended thinking is incompatible with
            # json_schema output_config and can produce unreliable results.

            return self.client.messages.create(**kwargs)

        try:
            response = await asyncio.to_thread(call_messages_structured)
            self.last_usage = extract_usage(response)
            text = self._extract_text_from_anthropic_message(response)
            if text:
                return self._parse_json_text(text)
            logger.warning("Anthropic parameter structured output returned no text; falling back to streaming request")
        except Exception as structured_error:
            logger.warning(
                "Anthropic parameter structured output failed; falling back to streaming request: %s",
                structured_error,
            )

        text, in_tokens, out_tokens, cached_tokens, thinking_tokens = await asyncio.to_thread(self._call_anthropic_streaming, user_content)
        total_input = in_tokens + (cached_tokens or 0)
        self.last_usage = {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "input_tokens": total_input,
            "cached_input_tokens": cached_tokens or 0,
            "output_tokens": out_tokens,
            "reasoning_tokens": thinking_tokens or 0,
            "total_tokens": total_input + out_tokens,
        }
        if text:
            return self._parse_json_text(text)
        return {"parameters": [], "extraction_notes": "No text content in response"}

    def _call_anthropic_streaming(self, user_content: str) -> tuple[str, int, int, int, int]:
        collected_text = ""
        in_tokens = 0
        out_tokens = 0
        cached_tokens = 0
        thinking_tokens = 0

        kwargs = {
            "model": self.model,
            "max_tokens": PARAM_MAX_OUTPUT_TOKENS,
            "system": [
                {
                    "type": "text",
                    "text": self.prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_content,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                }
            ],
            "temperature": 0.0,
            "stream": True,
        }

        if self.thinking_budget and self.thinking_budget > 0:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget
            }

        stream = self.client.messages.create(**kwargs)

        for event in stream:
            if hasattr(event, "type"):
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
                        thinking_tokens = getattr(event.message.usage, "thinking_tokens", 0) or 0

        return collected_text, in_tokens, out_tokens, cached_tokens, thinking_tokens

    def _extract_text_from_anthropic_message(self, response: Any) -> str:
        text_parts: List[str] = []
        content = getattr(response, "content", None) or []
        for block in content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_value = getattr(block, "text", None)
                if text_value:
                    text_parts.append(text_value)
        return "".join(text_parts)

    def _parse_json_text(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError as de:
            logger.warning("JSONDecodeError on text output: %s. Attempting repair.", de)
            try:
                rr = self.json_repair.repair(text)
                if rr.success and isinstance(rr.data, dict):
                    return rr.data
            except Exception as re:
                logger.error("JSONRepair failed: %s", re)
            logger.error("Raw text that failed parsing: %s", text)
        return {"parameters": []}

    @staticmethod
    def filter_by_action(parameters: List[Dict[str, Any]], statuses: List[str]) -> List[Dict[str, Any]]:
        """
        Filter parameters by action status.

        Args:
            parameters: List of parameter dictionaries
            statuses: List of action_status values to include (e.g., ["Change Required", "Verify"])

        Returns:
            Filtered list of parameters matching any of the specified statuses
        """
        if not statuses:
            return parameters
        return [p for p in parameters if p.get("action_status") in statuses]

    @staticmethod
    def filter_by_priority(parameters: List[Dict[str, Any]], priorities: List[str]) -> List[Dict[str, Any]]:
        """
        Filter parameters by priority.
        
        Args:
            parameters: List of parameter dictionaries
            priorities: List of priority values to include (e.g., ["High", "Medium"])
            
        Returns:
            Filtered list of parameters matching any of the specified priorities
        """
        if not priorities:
            return parameters
        return [p for p in parameters if p.get("priority") in priorities]
    
    @staticmethod
    def get_summary_stats(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get summary statistics for parameters by action status and priority.
        
        Args:
            parameters: List of parameter dictionaries
            
        Returns:
            Dictionary with counts by action_status and priority
        """
        by_action = {
            ACTION_STATUS_CHANGE_REQUIRED: 0,
            ACTION_STATUS_VERIFY: 0,
            ACTION_STATUS_NO_ACTION: 0,
            ACTION_STATUS_MONITOR: 0,
        }
        by_priority = {
            PRIORITY_HIGH: 0,
            PRIORITY_MEDIUM: 0,
            PRIORITY_LOW: 0,
        }
        
        for param in parameters:
            action = param.get("action_status", ACTION_STATUS_NO_ACTION)
            priority = param.get("priority", PRIORITY_LOW)
            
            if action in by_action:
                by_action[action] += 1
            if priority in by_priority:
                by_priority[priority] += 1
        
        return {
            "total": len(parameters),
            "by_action_status": by_action,
            "by_priority": by_priority,
            "actionable": by_action[ACTION_STATUS_CHANGE_REQUIRED] + by_action[ACTION_STATUS_VERIFY],
        }
    
    async def _call_api(self, markdown_content: str) -> Dict[str, Any]:
        """Call the OpenAI API with structured output."""
        
        # Prepare strict schema for structured outputs
        strict_schema = self._make_strict_schema(self.schema)
        
        text_format = {
            "format": {
                "type": "json_schema",
                "name": "extract_parameters",
                "schema": strict_schema,
                "strict": True,
            }
        }

        # Construct message content for Prompt Caching:
        # 1. Document content first (large static prefix)
        # 2. Instructions second
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text", 
                        "text": markdown_content
                    },
                    {
                        "type": "input_text", 
                        "text": self.prompt
                    }
                ]
            }
        ]

        def extract_usage(response: Any) -> Dict[str, Any]:
            usage = getattr(response, "usage", None)
            if hasattr(usage, "model_dump"):
                usage = usage.model_dump()
            elif usage is not None and not isinstance(usage, dict):
                usage = {
                    "input_tokens": getattr(usage, "input_tokens", None),
                    "output_tokens": getattr(usage, "output_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                    "input_tokens_details": getattr(usage, "input_tokens_details", None),
                    "output_tokens_details": getattr(usage, "output_tokens_details", None),
                }

            input_details = (usage or {}).get("input_tokens_details") or {}
            output_details = (usage or {}).get("output_tokens_details") or {}

            if hasattr(input_details, "model_dump"):
                input_details = input_details.model_dump()
            elif not isinstance(input_details, dict):
                input_details = {"cached_tokens": getattr(input_details, "cached_tokens", None)}

            if hasattr(output_details, "model_dump"):
                output_details = output_details.model_dump()
            elif not isinstance(output_details, dict):
                output_details = {"reasoning_tokens": getattr(output_details, "reasoning_tokens", None)}

            return {
                "model": self.model,
                "reasoning_effort": PARAM_REASONING_EFFORT,
                "input_tokens": (usage or {}).get("input_tokens"),
                "cached_input_tokens": input_details.get("cached_tokens", 0) or 0,
                "output_tokens": (usage or {}).get("output_tokens"),
                "reasoning_tokens": output_details.get("reasoning_tokens", 0) or 0,
                "total_tokens": (usage or {}).get("total_tokens"),
            }
        
        # Call API using responses endpoint with medium reasoning effort
        response = await asyncio.to_thread(
            lambda: self.client.responses.create(
                model=self.model,
                input=messages,
                text=text_format,
                reasoning={"effort": PARAM_REASONING_EFFORT},
                max_output_tokens=PARAM_MAX_OUTPUT_TOKENS,
            )
        )
        self.last_usage = extract_usage(response)
        
        # Log token usage
        try:
            logger.info(
                "Token usage: input_tokens=%s, cached_input_tokens=%s, output_tokens=%s, reasoning_tokens=%s, total_tokens=%s",
                self.last_usage.get("input_tokens"),
                self.last_usage.get("cached_input_tokens"),
                self.last_usage.get("output_tokens"),
                self.last_usage.get("reasoning_tokens"),
                self.last_usage.get("total_tokens"),
            )
        except Exception:
            logger.exception("Failed to read token usage")
        
        # Extract structured output
        try:
            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                    return parsed[0]
        except Exception as e:
            logger.warning("Failed to extract output_parsed: %s", e)
        
        # Fallback to output_text
        text = getattr(response, "output_text", None)
        if text:
            return self._parse_json_text(text)
        else:
            logger.warning("Both output_parsed and output_text were None or empty. Response: %s", response)
        
        return {"parameters": []}
    
    def _make_strict_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure schema has additionalProperties: false on all objects."""
        import copy
        
        def visit(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    node["additionalProperties"] = False
                    if "properties" in node:
                        for k, v in node["properties"].items():
                            node["properties"][k] = visit(v)
                if "items" in node:
                    node["items"] = visit(node["items"])
            return node
        
        return visit(copy.deepcopy(schema))
