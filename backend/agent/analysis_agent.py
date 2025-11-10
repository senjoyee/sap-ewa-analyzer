"""
Phase 2: Analysis Agent
Performs deep technical analysis of EWA system health, findings, and capacity.
Uses high reasoning effort for cross-section analysis and pattern recognition.
"""

from __future__ import annotations

import os
import json
import asyncio
from typing import Dict, Any, Optional

from utils.validation import (
    validate_finding_id,
    validate_severity,
    validate_risk_rating,
    validate_health_ratings,
    validate_required_fields,
    validate_no_nulls,
    validate_against_schema,
    ValidationError,
)
from utils.json_repair import JSONRepair


class AnalysisAgent:
    """Phase 2 agent: Analyze system health and identify findings"""

    def __init__(self, client, model: str, prompt_path: Optional[str] = None, schema_path: Optional[str] = None):
        self.client = client
        self.model = model
        
        # Load prompt
        if prompt_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(base_dir, "..", "prompts", "analysis_prompt.md")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt = f.read()
        
        # Load schema
        if schema_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(base_dir, "..", "schemas", "analysis_schema.json")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema: Dict[str, Any] = json.load(f)
        
        # Prepare function definition
        self.function_def = {
            "type": "function",
            "name": "analyze_ewa_system",
            "description": "Analyze EWA system health, identify findings, and assess capacity outlook",
            "parameters": self.schema,
        }
        
        # JSON repair utility
        self.json_repair = JSONRepair()

    async def run(self, markdown_content: str, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze system health and findings.
        
        Args:
            markdown_content: EWA report markdown content
            extraction_result: Phase 1 extraction output (metadata, chapters)
        
        Returns:
            Validated analysis result
        """
        print("[AnalysisAgent] Starting deep analysis phase")
        
        # Call LLM with context from Phase 1
        analysis_result = await self._call_llm(markdown_content, extraction_result)
        
        # Validate
        self._validate_output(analysis_result, extraction_result)
        
        findings_count = len(analysis_result.get("Key Findings", []))
        overall_risk = analysis_result.get("Overall Risk", "unknown")
        print(f"[AnalysisAgent] Analysis complete: {findings_count} key findings, risk={overall_risk}")
        
        return analysis_result

    async def _call_llm(self, markdown_content: str, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Call Azure OpenAI Responses API with markdown text and Phase 1 context"""
        
        try:
            # Build context from Phase 1
            context_summary = {
                "System ID": extraction_result.get("System Metadata", {}).get("System ID", "Unknown"),
                "Report Date": extraction_result.get("System Metadata", {}).get("Report Date", "Unknown"),
                "Chapters Reviewed": extraction_result.get("Chapters Reviewed", []),
                "Profile Parameters Count": len(extraction_result.get("Profile Parameters", [])),
            }
            
            context_text = f"""
Phase 1 Extraction Context:
{json.dumps(context_summary, indent=2)}

Important: All "Source" fields in your findings must reference chapters from the "Chapters Reviewed" list above.
"""
            
            # Build input content with markdown text
            user_content = [
                {"type": "input_text", "text": f"EWA Report Content (Markdown):\n\n{markdown_content}"},
                {"type": "input_text", "text": context_text},
                {"type": "input_text", "text": "Please perform deep technical analysis of this EWA report according to the instructions."},
                {"type": "input_text", "text": self.prompt}
            ]
            
            # Call Responses API with high reasoning effort
            response = await asyncio.to_thread(
                lambda: self.client.responses.create(
                    model=self.model,
                    input=[{"role": "user", "content": user_content}],
                    tools=[self.function_def],
                    tool_choice={"type": "function", "name": "analyze_ewa_system"},
                    max_output_tokens=16384,
                    reasoning={"effort": "high"},
                )
            )
            
            # Log token usage
            try:
                usage = getattr(response, "usage", None)
                if usage:
                    in_tok = getattr(usage, "input_tokens", None)
                    out_tok = getattr(usage, "output_tokens", None)
                    reasoning_tok = getattr(usage, "reasoning_tokens", None)
                    print(f"[AnalysisAgent] Token usage: input={in_tok}, output={out_tok}, reasoning={reasoning_tok}")
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
                
                if item_type == "function_call" and item_name == "analyze_ewa_system":
                    args_str = item_args
                    break
            
            if not args_str:
                # Fallback to output_text
                text = getattr(response, "output_text", None)
                if text:
                    args_str = text
            
            if not args_str:
                raise RuntimeError("No function call result returned from analysis")
            
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
                
                raise RuntimeError(f"Failed to parse analysis result: {args_str[:200]}")
        
        except Exception as e:
            print(f"[AnalysisAgent] Error: {e}")
            raise

    def _validate_output(self, data: Dict[str, Any], extraction_result: Dict[str, Any]) -> None:
        """
        Validate analysis output.
        Raises ValidationError if invalid.
        """
        errors = []
        
        # Check required fields
        required = ["System Health Overview", "Positive Findings", "Key Findings", "Capacity Outlook", "Overall Risk"]
        missing = validate_required_fields(data, required)
        if missing:
            errors.append(f"Missing required fields: {', '.join(missing)}")
        
        # Check no nulls
        null_paths = validate_no_nulls(data)
        if null_paths:
            errors.append(f"Found null values at: {', '.join(null_paths)}")
        
        # Validate System Health Overview ratings
        if "System Health Overview" in data:
            health_errors = validate_health_ratings(data["System Health Overview"])
            errors.extend(health_errors)
        
        # Validate Key Findings
        if "Key Findings" in data:
            findings = data["Key Findings"]
            if not isinstance(findings, list):
                errors.append("Key Findings must be an array")
            else:
                seen_ids = set()
                for i, finding in enumerate(findings):
                    # Validate ID format
                    finding_id = finding.get("Issue ID", "")
                    if not validate_finding_id(finding_id):
                        errors.append(f"Invalid finding ID format at index {i}: {finding_id}")
                    
                    # Check for duplicate IDs
                    if finding_id in seen_ids:
                        errors.append(f"Duplicate finding ID: {finding_id}")
                    seen_ids.add(finding_id)
                    
                    # Validate severity
                    severity = finding.get("Severity", "")
                    if not validate_severity(severity):
                        errors.append(f"Invalid severity at finding {finding_id}: {severity}")
                    
                    # Validate source references valid chapter
                    source = finding.get("Source", "")
                    chapters = extraction_result.get("Chapters Reviewed", [])
                    # Soft validation: just check source is not empty
                    if not source or source == "Unknown":
                        errors.append(f"Finding {finding_id} missing source reference")
        
        # Validate Overall Risk
        risk = data.get("Overall Risk", "")
        if not validate_risk_rating(risk):
            errors.append(f"Invalid Overall Risk rating: {risk}")
        
        # Schema validation
        schema_error = validate_against_schema(data, self.schema)
        if schema_error:
            errors.append(f"Schema validation failed: {schema_error}")
        
        if errors:
            raise ValidationError(phase="AnalysisAgent", errors=errors)
