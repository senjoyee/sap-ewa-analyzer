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
    """Agent for extracting parameter recommendations using GPT-5.1."""
    
    def __init__(self, client, model: str = None):
        """
        Initialize the parameter extraction agent.
        
        Args:
            client: Azure OpenAI client instance
            model: Model deployment name (defaults to AZURE_OPENAI_PARAM_MODEL or gpt-5.1)
        """
        self.client = client
        # Use gpt-5.1 specifically for parameter extraction
        self.model = model or os.getenv("AZURE_OPENAI_PARAM_MODEL", "gpt-5.1")
        
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
            result = await self._call_api(markdown_content)
            
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
        
        # Call API using responses endpoint with medium reasoning effort
        response = await asyncio.to_thread(
            lambda: self.client.responses.create(
                model=self.model,
                input=messages,
                text=text_format,
                reasoning={"effort": "none"},
                max_output_tokens=16384,
            )
        )
        
        # Log token usage
        try:
            usage = getattr(response, "usage", None)
            if usage:
                in_tok = getattr(usage, "input_tokens", None)
                out_tok = getattr(usage, "output_tokens", None)
                logger.info("Token usage: input=%s, output=%s", in_tok, out_tok)
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
        except Exception:
            pass
        
        # Fallback to output_text
        text = getattr(response, "output_text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        
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
