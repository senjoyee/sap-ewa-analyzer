"""
Phase 1: Extraction Agent
Extracts structured metadata and raw data from EWA PDF reports.
Uses cost-efficient model (gpt-4o-mini) for mechanical extraction tasks.
"""

from __future__ import annotations

import os
import json
import asyncio
from typing import Dict, Any, Optional

from utils.validation import (
    validate_sid,
    validate_date_format,
    validate_required_fields,
    validate_no_nulls,
    validate_against_schema,
    ValidationError,
)
from utils.json_repair import JSONRepair


class ExtractionAgent:
    """Phase 1 agent: Extract metadata and raw data from EWA PDF"""

    def __init__(self, client, model: str, prompt_path: Optional[str] = None, schema_path: Optional[str] = None):
        self.client = client
        self.model = model
        
        # Load prompt
        if prompt_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(base_dir, "..", "prompts", "extraction_prompt.md")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt = f.read()
        
        # Load schema
        if schema_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(base_dir, "..", "schemas", "extraction_schema.json")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema: Dict[str, Any] = json.load(f)
        
        # Prepare function definition
        self.function_def = {
            "type": "function",
            "name": "extract_ewa_metadata",
            "description": "Extract structured metadata and raw data from EWA PDF report",
            "parameters": self.schema,
        }
        
        # JSON repair utility
        self.json_repair = JSONRepair()

    async def run(self, markdown_content: str) -> Dict[str, Any]:
        """
        Extract metadata from EWA markdown content.
        Returns validated extraction result.
        """
        print("[ExtractionAgent] Starting extraction phase")
        
        # Call LLM
        extraction_result = await self._call_llm(markdown_content)
        
        # Validate
        self._validate_output(extraction_result)
        
        print(f"[ExtractionAgent] Extraction complete: {len(extraction_result.get('Chapters Reviewed', []))} chapters, "
              f"{len(extraction_result.get('Profile Parameters', []))} parameters")
        
        return extraction_result

    async def _call_llm(self, markdown_content: str) -> Dict[str, Any]:
        """Call Azure OpenAI Responses API with markdown text input"""
        
        try:
            # Build input content with markdown text
            user_content = [
                {"type": "input_text", "text": f"EWA Report Content (Markdown):\n\n{markdown_content}"},
                {"type": "input_text", "text": "Please extract the metadata from this EWA report according to the instructions."},
                {"type": "input_text", "text": self.prompt}
            ]
            
            # Call Responses API with function calling
            response = await asyncio.to_thread(
                lambda: self.client.responses.create(
                    model=self.model,
                    input=[{"role": "user", "content": user_content}],
                    tools=[self.function_def],
                    tool_choice={"type": "function", "name": "extract_ewa_metadata"},
                    max_output_tokens=4096,
                    reasoning={"effort": "low"},
                )
            )
            
            # Log token usage
            try:
                usage = getattr(response, "usage", None)
                if usage:
                    in_tok = getattr(usage, "input_tokens", None)
                    out_tok = getattr(usage, "output_tokens", None)
                    print(f"[ExtractionAgent] Token usage: input={in_tok}, output={out_tok}")
            except Exception:
                pass
            
            # Parse function call result
            args_str = None
            for item in getattr(response, "output", []) or []:
                try:
                    item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                    item_name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None)
                    item_args = getattr(item, "arguments", None) or (item.get("arguments") if isinstance(item, dict) else None)
                except Exception:
                    continue
                
                if item_type == "function_call" and item_name == "extract_ewa_metadata":
                    args_str = item_args
                    break
            
            if not args_str:
                # Fallback to output_text
                text = getattr(response, "output_text", None)
                if text:
                    args_str = text
            
            if not args_str:
                raise RuntimeError("No function call result returned from extraction")
            
            # Parse JSON
            if isinstance(args_str, dict):
                return args_str
            
            try:
                return json.loads(args_str)
            except Exception:
                # Attempt repair
                rr = self.json_repair.repair(args_str)
                if rr.success and isinstance(rr.data, dict):
                    return rr.data
                
                # Try extracting JSON substring
                start = args_str.find("{")
                end = args_str.rfind("}")
                if start != -1 and end != -1 and end > start:
                    candidate = args_str[start:end+1]
                    return json.loads(candidate)
                
                raise RuntimeError(f"Failed to parse extraction result: {args_str[:200]}")
        
        except Exception as e:
            print(f"[ExtractionAgent] Error: {e}")
            raise

    def _validate_output(self, data: Dict[str, Any]) -> None:
        """
        Validate extraction output.
        Raises ValidationError if invalid.
        """
        errors = []
        
        # Check required fields
        required = ["System Metadata", "Chapters Reviewed", "Profile Parameters", "Raw Capacity Data"]
        missing = validate_required_fields(data, required)
        if missing:
            errors.append(f"Missing required fields: {', '.join(missing)}")
        
        # Check no nulls
        null_paths = validate_no_nulls(data)
        if null_paths:
            errors.append(f"Found null values at: {', '.join(null_paths)}")
        
        # Validate System Metadata
        if "System Metadata" in data:
            metadata = data["System Metadata"]
            
            sid = metadata.get("System ID", "")
            if not validate_sid(sid):
                errors.append(f"Invalid System ID format: {sid} (must be 3 uppercase letters)")
            
            report_date = metadata.get("Report Date", "")
            if not validate_date_format(report_date):
                errors.append(f"Invalid Report Date format: {report_date} (must be dd.mm.yyyy)")
        
        # Validate Chapters Reviewed not empty
        chapters = data.get("Chapters Reviewed", [])
        if not isinstance(chapters, list) or len(chapters) == 0:
            errors.append("Chapters Reviewed must be a non-empty array")
        
        # Schema validation
        schema_error = validate_against_schema(data, self.schema)
        if schema_error:
            errors.append(f"Schema validation failed: {schema_error}")
        
        if errors:
            raise ValidationError(phase="ExtractionAgent", errors=errors)
