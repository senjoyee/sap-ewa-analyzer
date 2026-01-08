"""
Parameter Extraction Agent using GPT-5-mini for extracting SAP parameter recommendations.
Runs as a post-processing step after main EWA analysis to extract parameter changes from markdown.
"""
from __future__ import annotations

import os
import json
import asyncio
from typing import Dict, Any, List, Optional

# Schema for parameter extraction
PARAMETER_SCHEMA = {
    "type": "object",
    "properties": {
        "parameters": {
            "type": "array",
            "description": "List of all recommended parameter changes found in the document",
            "items": {
                "type": "object",
                "properties": {
                    "parameter_name": {
                        "type": "string",
                        "description": "The exact parameter name (e.g., rdisp/wp_no_dia, global_allocation_limit)"
                    },
                    "area": {
                        "type": "string",
                        "enum": ["SAP HANA", "Database", "SAP Kernel", "Profile Parameters", "Application", "Memory/Buffer", "Operating System", "Network", "General"],
                        "description": "The category/layer this parameter belongs to"
                    },
                    "current_value": {
                        "type": "string",
                        "description": "The current configured value (empty string if not specified)"
                    },
                    "recommended_value": {
                        "type": "string",
                        "description": "The SAP recommended or target value"
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what this parameter controls"
                    },
                    "source_section": {
                        "type": "string",
                        "description": "The section/chapter in the document where this parameter was found"
                    }
                },
                "required": ["parameter_name", "area", "current_value", "recommended_value", "description", "source_section"],
                "additionalProperties": False
            }
        },
        "extraction_notes": {
            "type": "string",
            "description": "Any notes about the extraction process or data quality"
        }
    },
    "required": ["parameters", "extraction_notes"],
    "additionalProperties": False
}

EXTRACTION_PROMPT = """You are an expert SAP Basis consultant. Your task is to extract ALL recommended parameter changes from this SAP EarlyWatch Alert (EWA) report.

IMPORTANT INSTRUCTIONS:
1. Extract ONLY actual SAP parameters - technical configuration settings with specific names like:
   - Profile parameters: rdisp/wp_no_dia, abap/heap_area_dia, icm/server_port_0
   - HANA parameters: global_allocation_limit, parallel_merge_threads
   - Database parameters: max_connections, shared_pool_size
   - Kernel parameters: em/initial_size_MB, rdisp/tm_max_no

2. DO NOT extract:
   - General recommendations that are not parameter changes
   - Findings or issues without specific parameter values
   - Section headers or table labels
   - Narrative text that mentions parameters without recommending changes

3. For each parameter found, extract:
   - parameter_name: The exact technical parameter name
   - area: Categorize as SAP HANA, Database, SAP Kernel, Profile Parameters, Application, Memory/Buffer, Operating System, Network, or General
   - current_value: The current value if mentioned (empty string if not specified)
   - recommended_value: The target/recommended value
   - description: Brief description of the parameter's purpose
   - source_section: Which section of the report this came from

4. Look for parameters in:
   - Tables with columns like "Parameter", "Current", "Recommended", "Target"
   - Sections about configuration, tuning, optimization
   - HANA alerts and recommendations
   - Profile parameter recommendations
   - Memory and buffer settings

5. If no valid parameters are found, return an empty array.

Analyze the following EWA report and extract all parameter recommendations:

"""


class ParameterExtractionAgent:
    """Agent for extracting parameter recommendations using GPT-5-mini."""
    
    def __init__(self, client, model: str = None):
        """
        Initialize the parameter extraction agent.
        
        Args:
            client: Azure OpenAI client instance
            model: Model deployment name (defaults to AZURE_OPENAI_FAST_MODEL or gpt-4.1-mini)
        """
        self.client = client
        # Use gpt-5-mini specifically for parameter extraction
        self.model = model or os.getenv("AZURE_OPENAI_PARAM_MODEL", "gpt-5-mini")
        self.schema = PARAMETER_SCHEMA
        self.prompt = EXTRACTION_PROMPT
    
    async def extract(self, markdown_content: str) -> Dict[str, Any]:
        """
        Extract parameter recommendations from markdown content.
        
        Args:
            markdown_content: The EWA report markdown content
            
        Returns:
            Dictionary with 'parameters' list and optional 'extraction_notes'
        """
        if not markdown_content or not markdown_content.strip():
            return {"parameters": [], "extraction_notes": "Empty input content"}
        
        try:
            result = await self._call_api(markdown_content)
            
            # Validate result structure
            if not isinstance(result, dict):
                return {"parameters": [], "extraction_notes": "Invalid response format"}
            
            parameters = result.get("parameters", [])
            if not isinstance(parameters, list):
                parameters = []
            
            # Filter out invalid entries
            valid_params = []
            for param in parameters:
                if isinstance(param, dict) and param.get("parameter_name"):
                    # Ensure required fields exist
                    valid_params.append({
                        "parameter_name": str(param.get("parameter_name", "")),
                        "area": str(param.get("area", "General")),
                        "current_value": str(param.get("current_value", "")),
                        "recommended_value": str(param.get("recommended_value", "")),
                        "description": str(param.get("description", "")),
                        "source_section": str(param.get("source_section", "")),
                    })
            
            print(f"[ParameterExtractionAgent] Extracted {len(valid_params)} valid parameters")
            
            return {
                "parameters": valid_params,
                "extraction_notes": result.get("extraction_notes", "")
            }
            
        except Exception as e:
            print(f"[ParameterExtractionAgent] Error during extraction: {e}")
            return {"parameters": [], "extraction_notes": f"Extraction error: {str(e)}"}
    
    async def _call_api(self, markdown_content: str) -> Dict[str, Any]:
        """Call the OpenAI API with structured output."""
        
        # Truncate content if too long (keep first ~100k chars to stay within token limits)
        max_chars = 100000
        if len(markdown_content) > max_chars:
            markdown_content = markdown_content[:max_chars] + "\n\n[Content truncated...]"
        
        user_message = f"{self.prompt}\n\n{markdown_content}"
        
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
        
        # Call API using responses endpoint with medium reasoning effort
        response = await asyncio.to_thread(
            lambda: self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": [{"type": "input_text", "text": user_message}]}],
                text=text_format,
                reasoning={"effort": "medium"},
                max_output_tokens=16384,
            )
        )
        
        # Log token usage
        try:
            usage = getattr(response, "usage", None)
            if usage:
                in_tok = getattr(usage, "input_tokens", None)
                out_tok = getattr(usage, "output_tokens", None)
                print(f"[ParameterExtractionAgent] Token usage: input={in_tok}, output={out_tok}")
        except Exception:
            pass
        
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
