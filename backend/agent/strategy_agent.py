"""
Phase 3: Strategy Agent
Generates executive summary and actionable recommendations based on analysis findings.
Uses medium reasoning effort for structured strategic planning.
"""

from __future__ import annotations

import os
import json
import asyncio
from typing import Dict, Any, Optional, List

from utils.validation import (
    validate_recommendation_id,
    validate_linkage,
    validate_effort_structure,
    validate_medium_high_critical_coverage,
    validate_required_fields,
    validate_no_nulls,
    validate_against_schema,
    ValidationError,
)
from utils.json_repair import JSONRepair


class StrategyAgent:
    """Phase 3 agent: Create recommendations and executive summary"""

    def __init__(self, client, model: str, prompt_path: Optional[str] = None, schema_path: Optional[str] = None):
        self.client = client
        self.model = model
        
        # Load prompt
        if prompt_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(base_dir, "..", "prompts", "strategy_prompt.md")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt = f.read()
        
        # Load schema
        if schema_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(base_dir, "..", "schemas", "strategy_schema.json")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema: Dict[str, Any] = json.load(f)
        
        # Prepare function definition
        self.function_def = {
            "type": "function",
            "name": "create_ewa_strategy",
            "description": "Generate executive summary and actionable recommendations",
            "parameters": self.schema,
        }
        
        # JSON repair utility
        self.json_repair = JSONRepair()

    async def run(
        self, 
        extraction_result: Dict[str, Any], 
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate strategic recommendations.
        
        Args:
            extraction_result: Phase 1 extraction output
            analysis_result: Phase 2 analysis output
        
        Returns:
            Validated strategy result
        """
        print("[StrategyAgent] Starting strategy phase")
        
        # Call LLM with context from Phase 1 & 2
        strategy_result = await self._call_llm(extraction_result, analysis_result)
        
        # Validate
        self._validate_output(strategy_result, analysis_result)
        
        rec_count = len(strategy_result.get("Recommendations", []))
        print(f"[StrategyAgent] Strategy complete: {rec_count} recommendations generated")
        
        return strategy_result

    async def _call_llm(
        self, 
        extraction_result: Dict[str, Any], 
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call Azure OpenAI Responses API with Phase 1 & 2 context"""
        
        try:
            # Build comprehensive context from previous phases
            key_findings = analysis_result.get("Key Findings", [])
            
            # Filter medium/high/critical findings for context
            critical_findings = [
                f for f in key_findings 
                if f.get("Severity") in ["medium", "high", "critical"]
            ]
            
            context_summary = {
                "System ID": extraction_result.get("System Metadata", {}).get("System ID", "Unknown"),
                "Report Date": extraction_result.get("System Metadata", {}).get("Report Date", "Unknown"),
                "Overall Risk": analysis_result.get("Overall Risk", "unknown"),
                "System Health Overview": analysis_result.get("System Health Overview", {}),
                "Key Findings Count": len(key_findings),
                "Critical Findings Requiring Recommendations": critical_findings,
                "Capacity Outlook Summary": analysis_result.get("Capacity Outlook", {}).get("Summary", ""),
            }
            
            context_text = f"""
Phase 1 & 2 Analysis Context:
{json.dumps(context_summary, indent=2)}

Important Rules:
1. Create ONE recommendation for EACH medium/high/critical finding listed above
2. Total recommendations must be >= {len(critical_findings)}
3. Each recommendation's "Linked issue ID" must match a finding's "Issue ID" from the list above
4. Use newline-delimited markdown bullets for Action and Preventative Action fields
5. Estimated Effort must be an object with "analysis" and "implementation" keys
"""
            
            # Build input content (no PDF needed for strategy)
            user_content = [
                {"type": "input_text", "text": context_text},
                {"type": "input_text", "text": "Please generate the executive summary and recommendations according to the instructions."},
                {"type": "input_text", "text": self.prompt}
            ]
            
            # Call Responses API with medium reasoning effort
            response = await asyncio.to_thread(
                lambda: self.client.responses.create(
                    model=self.model,
                    input=[{"role": "user", "content": user_content}],
                    tools=[self.function_def],
                    tool_choice={"type": "function", "name": "create_ewa_strategy"},
                    max_output_tokens=12288,
                    reasoning={"effort": "medium"},
                )
            )
            
            # Log token usage
            try:
                usage = getattr(response, "usage", None)
                if usage:
                    in_tok = getattr(usage, "input_tokens", None)
                    out_tok = getattr(usage, "output_tokens", None)
                    reasoning_tok = getattr(usage, "reasoning_tokens", None)
                    print(f"[StrategyAgent] Token usage: input={in_tok}, output={out_tok}, reasoning={reasoning_tok}")
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
                
                if item_type == "function_call" and item_name == "create_ewa_strategy":
                    args_str = item_args
                    break
            
            if not args_str:
                # Fallback to output_text
                text = getattr(response, "output_text", None)
                if text:
                    args_str = text
            
            if not args_str:
                raise RuntimeError("No function call result returned from strategy")
            
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
                
                raise RuntimeError(f"Failed to parse strategy result: {args_str[:200]}")
        
        except Exception as e:
            print(f"[StrategyAgent] Error: {e}")
            raise

    def _validate_output(self, data: Dict[str, Any], analysis_result: Dict[str, Any]) -> None:
        """
        Validate strategy output.
        Raises ValidationError if invalid.
        """
        errors = []
        
        # Check required fields
        required = ["Executive Summary", "Recommendations"]
        missing = validate_required_fields(data, required)
        if missing:
            errors.append(f"Missing required fields: {', '.join(missing)}")
        
        # Check no nulls
        null_paths = validate_no_nulls(data)
        if null_paths:
            errors.append(f"Found null values at: {', '.join(null_paths)}")
        
        # Validate Recommendations
        if "Recommendations" in data:
            recommendations = data["Recommendations"]
            if not isinstance(recommendations, list):
                errors.append("Recommendations must be an array")
            else:
                seen_ids = set()
                for i, rec in enumerate(recommendations):
                    # Validate ID format
                    rec_id = rec.get("Recommendation ID", "")
                    if not validate_recommendation_id(rec_id):
                        errors.append(f"Invalid recommendation ID format at index {i}: {rec_id}")
                    
                    # Check for duplicate IDs
                    if rec_id in seen_ids:
                        errors.append(f"Duplicate recommendation ID: {rec_id}")
                    seen_ids.add(rec_id)
                    
                    # Validate effort structure
                    effort = rec.get("Estimated Effort", {})
                    effort_errors = validate_effort_structure(effort)
                    if effort_errors:
                        errors.extend([f"Recommendation {rec_id}: {err}" for err in effort_errors])
                
                # Validate linkages to Phase 2 findings
                findings = analysis_result.get("Key Findings", [])
                linkage_errors = validate_linkage(recommendations, findings)
                errors.extend(linkage_errors)
                
                # Validate coverage of medium/high/critical findings
                coverage_errors = validate_medium_high_critical_coverage(findings, recommendations)
                errors.extend(coverage_errors)
        
        # Validate Executive Summary is not empty
        exec_summary = data.get("Executive Summary", "")
        if not exec_summary or exec_summary.strip() == "":
            errors.append("Executive Summary cannot be empty")
        
        # Schema validation
        schema_error = validate_against_schema(data, self.schema)
        if schema_error:
            errors.append(f"Schema validation failed: {schema_error}")
        
        if errors:
            raise ValidationError(phase="StrategyAgent", errors=errors)
