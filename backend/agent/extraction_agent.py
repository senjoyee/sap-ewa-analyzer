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
import re
from datetime import datetime


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
        
        # Log raw extraction for debugging
        if "System Metadata" in extraction_result:
            raw_date = extraction_result["System Metadata"].get("Report Date", "")
            print(f"[ExtractionAgent] Raw extracted date: '{raw_date}'")
        
        # Validate (includes auto-correction)
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

    def _guess_malformed_date(self, p1: str, p2: str, p3: str, p4: str) -> str:
        """
        Try to guess the correct date from malformed patterns like "0301-11-20".
        Args: p1, p2, p3, p4 are the 4 captured groups from the regex
        """
        # Try to interpret as: p3 (month) and p4 (day in YY format) → assume 20YY
        # Example: "0301-11-20" → month=11, day=20, year=2003 or 2020?
        # Better guess: use p3 as month, p4 as day, construct year from p1+p2
        try:
            # Attempt 1: p1p2 as year (03 01 → 2003 or 2301?), p3 as month, p4 as day
            year_candidate = int(p1 + p2)
            if year_candidate < 100:
                year_candidate += 2000  # 03 → 2003, 25 → 2025
            month = int(p3)
            day = int(p4)
            
            # Validate ranges
            if 1 <= month <= 12 and 1 <= day <= 31 and 2000 <= year_candidate <= 2100:
                return f"{str(day).zfill(2)}.{str(month).zfill(2)}.{year_candidate}"
        except Exception:
            pass
        
        # Attempt 2: p3 as month, p4 as day, assume current year 2025
        try:
            month = int(p3)
            day = int(p4)
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{str(day).zfill(2)}.{str(month).zfill(2)}.2025"
        except Exception:
            pass
        
        return f"{p1}{p2}-{p3}-{p4}"  # Return original if can't parse

    def _fix_date_format(self, date_str: str) -> str:
        """
        Attempt to auto-correct common date format errors.
        Returns corrected date in dd.mm.yyyy format or original if unable to parse.
        """
        if not date_str or not isinstance(date_str, str):
            return date_str
        
        # Already correct format
        if re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
            return date_str
        
        # Try common patterns
        patterns = [
            (r'^(\d{4})-(\d{2})-(\d{2})$', lambda m: f"{m.group(3)}.{m.group(2)}.{m.group(1)}"),  # 2025-11-02
            (r'^(\d{2})/(\d{2})/(\d{4})$', lambda m: f"{m.group(1)}.{m.group(2)}.{m.group(3)}"),  # 02/11/2025
            (r'^(\d{4})(\d{2})(\d{2})$', lambda m: f"{m.group(3)}.{m.group(2)}.{m.group(1)}"),    # 20251102
            (r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', lambda m: f"{m.group(1).zfill(2)}.{m.group(2).zfill(2)}.{m.group(3)}"),  # 2.11.2025
            # Handle malformed dates like "0301-11-20" or "0311-11-03"
            # Pattern: DDMM-MM-YY or MMDD-MM-YY → try to extract reasonable date
            (r'^(\d{2})(\d{2})-(\d{2})-(\d{2})$', lambda m: self._guess_malformed_date(m.group(1), m.group(2), m.group(3), m.group(4))),
        ]
        
        for pattern, formatter in patterns:
            match = re.match(pattern, date_str)
            if match:
                try:
                    return formatter(match)
                except Exception:
                    continue
        
        # Try parsing with datetime as last resort
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d.%m.%Y', '%Y%m%d']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%d.%m.%Y')
            except Exception:
                continue
        
        return date_str

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
                errors.append(f"Invalid System ID format: {sid} (must be 3 uppercase characters)")
            
            report_date = metadata.get("Report Date", "")
            # Try to auto-fix date format
            if report_date and not validate_date_format(report_date):
                fixed_date = self._fix_date_format(report_date)
                if validate_date_format(fixed_date):
                    print(f"[ExtractionAgent] Auto-corrected date: {report_date} → {fixed_date}")
                    metadata["Report Date"] = fixed_date
                    report_date = fixed_date
                else:
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
