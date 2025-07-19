"""Agent responsible for producing a structured JSON summary for an SAP EWA report using Azure OpenAI function-calling."""
from __future__ import annotations

import os
import json
import asyncio
from typing import Dict, Any
from jsonschema import validate, ValidationError

# Fallback prompt if not supplied
DEFAULT_PROMPT = """You are a world-class SAP Technical Quality Manager and strategic EWA analyst with 20 years of experience. Your task is to analyze the provided SAP EarlyWatch Alert (EWA) report markdown and generate a comprehensive, structured, and actionable executive summary in JSON format. Your analysis must be deep, insightful, and practical, focusing on business risk and proactive quality management.
Follow these instructions precisely, adhering to the structure of the requested JSON schema:
1.  **System Metadata**: Extract the System ID (SID), the report generation date, and the analysis period from the document.
2.  **System Health Overview**: Provide a quick at-a-glance rating (Good, Fair, Poor) for the key areas: Performance, Security, Stability, and Configuration.
3.  **Executive Summary**: Write a concise summary for a C-level audience, highlighting the overall system status, key business risks, and the most critical actions required. MAKE SURE IT USES BULLET POINTS.
4.  **Positive Findings**: Identify areas where the system is performing well or best practices are being followed. Note the area and a brief description.
5.  **Key Findings**: Detail important observations relevant for system health. For each finding, assign a unique ID (e.g., KF-001, KF-002, KF-003), specify the functional area, a description, its potential technical impact, and **translate this into a potential business impact** (e.g., 'Risk of delayed order processing'). Assign a severity level (Low, Medium, High, Critical).
6.  **Recommendations**: Create a list of clear, actionable recommendations. For each, specify a unique ID (e.g., REC-001), priority, the responsible area, the specific action to take, a **validation step** to confirm the fix, and a **preventative action** to stop recurrence. Break down the estimated effort into 'Analysis' and 'Implementation' (Low, Medium, High). Link it to a key finding ID (e.g., KF-001) if the recommendation addresses a specific key finding.
7.  **Quick Wins**: After generating all recommendations, create a separate `quickWins` list. Populate it with any recommendations you have marked as 'High' or 'Medium' priority but 'Low' for both analysis and implementation effort.
8.  **Trend Analysis**: Analyze historical data in the report (e.g. but not limited to, Average Dialog Response Time, DB Growth). Provide(if available), the **previous value, the current value, and the percentage change**. Then, provide an overall rating ("Improving", "Stable", "Degrading") for performance and stability, supported by these metrics. Be comprehensive in your analysis.
9.  **Capacity Outlook**: Analyze data on resource consumption. Provide a summary for database growth, CPU, and memory utilization, and give a consolidated outlook on future capacity needs.
10. **Profile Parameters**: Extract and list all relevant profile parameter changes recommended, across the stack (Application & Database). For each profile parameter, provide: name, area(like ABAP, JAVA, HANA, ORACLE, etc), current value, recommended value & description. Present this as an array in the JSON for tabular display. MAKE SURE ALL PROFILE PARAMETERS ACROSS THE DOCUMENT ARE CAPTURED.
11. **Benchmarking**: Based on your general knowledge of SAP systems, provide a brief benchmark analysis. For key metrics like response times or number of security alerts, comment on whether they are typical, high, or low for the system type.
12. **Overall Risk**: Based on your complete analysis, assign a single overall risk rating: Low, Medium, High, or Critical.
Ensure your entire output strictly adheres to the provided JSON schema. Do not add any commentary outside of the JSON structure."""

# Attempt to load prompt from prompts/ewa_summary_prompt.md (preferred over inline string)
DEFAULT_PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts", "ewa_summary_prompt.md")
if os.path.exists(DEFAULT_PROMPT_PATH):
    with open(DEFAULT_PROMPT_PATH, "r", encoding="utf-8") as _f:
        DEFAULT_PROMPT = _f.read()

class EWAAgent:
    """Small agent that plans (single step) and returns a validated JSON summary."""

    def __init__(self, client, model: str, summary_prompt: str | None = None, schema_path: str | None = None):
        self.client = client
        self.model = model
        self.summary_prompt = summary_prompt or DEFAULT_PROMPT

        if schema_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(base_dir, "..", "schemas", "ewa_summary_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema: Dict[str, Any] = json.load(f)

        # Prepare function definition for function-calling
        self.function_def = {
            "name": "create_ewa_summary",
            "description": "Return the structured executive summary for an EWA report in JSON that conforms to the schema.",
            "parameters": self.schema,
        }

    # ----------------------------- Public API ----------------------------- #
    async def run(self, markdown: str) -> Dict[str, Any]:
        """Return a validated summary JSON object. May attempt a single self-repair."""
        summary_json = await self._call_openai(markdown)
        if self._is_valid(summary_json):
            return summary_json

        # Try once to repair
        summary_json = await self._repair(markdown, summary_json)
        # Either returns valid JSON or last attempt regardless of validity
        return summary_json

    # ----------------------------- Internal helpers ----------------------------- #

    async def refine(self, markdown: str, draft_json: dict) -> dict:
        """Improve a first-pass JSON using self.model, then return the new JSON."""
        repair_prompt = (
            "Using the prior draft below, enhance depth, fill missing values, "
            "and return ONLY the corrected JSON object."
        )
        messages = [
            {"role": "system", "content": self.summary_prompt},
            {"role": "assistant", "content": json.dumps(draft_json)},
            {"role": "user", "content": repair_prompt},
        ]
        response = await self._async_openai(messages)
        return json.loads(response.choices[0].message.function_call.arguments)

    async def quality_control_refine(self, draft_json: dict) -> dict:
        """Apply quality control filtering and validation to first-pass JSON output.
        
        This method implements a reasoning model approach that:
        1. Filters Executive Summary for C-level appropriateness
        2. Reviews and validates Positive Findings
        3. Validates Key Findings and filters by severity (Critical/High/Medium only)
        4. Validates Recommendations and filters by severity (Critical/High/Medium only)
        5. Validates Capacity Outlook
        6. Returns everything else as-is
        """
        quality_control_prompt = """
You are a senior SAP Quality Assurance specialist and C-level advisor. Your task is to review and refine the provided EWA analysis JSON output from a first-pass analysis.

Your responsibilities are:

1. **Executive Summary Review**: 
   - Analyze each bullet point in the Executive Summary
   - Keep only items that are appropriate for a C-level audience (strategic, business-critical, high-impact)
   - Remove technical jargon or low-level operational details
   - Ensure each point clearly communicates business risk or opportunity

2. **Positive Findings Validation**:
   - Review each positive finding for relevance and accuracy
   - Reword items that are too technical for business stakeholders
   - Remove findings that are routine or not noteworthy
   - Ensure findings highlight genuine business value or risk mitigation

3. **Key Findings Quality Control**:
   - Validate that Impact sections accurately describe technical consequences
   - Verify Business Impact translations are meaningful and specific
   - Confirm Severity ratings are appropriate (Critical/High/Medium/Low)
   - **FILTER OUT all Low severity findings - retain only Critical, High, and Medium**
   - Correct any inaccuracies in impact assessment or severity rating

4. **Recommendations Validation**:
   - Verify each recommendation's Action is clear and actionable
   - Validate Estimated Effort assessments are realistic
   - Ensure Preventative Actions will prevent recurrence
   - Confirm Validation Steps will verify fix completion
   - **FILTER OUT all Low priority recommendations - retain only Critical, High, and Medium**

5. **Capacity Outlook Review**:
   - Validate capacity projections are reasonable and well-supported
   - Ensure outlook statements are clear and actionable
   - Correct any inconsistencies in capacity analysis

**IMPORTANT**: 
- You have access ONLY to the first-pass JSON output - no external data
- Return the complete JSON structure with all original sections
- Only modify the sections specified above
- All other sections (System Metadata, Trend Analysis, Profile Parameters, etc.) should be returned unchanged
- Maintain the exact JSON schema structure

Return ONLY the refined JSON object.
"""

        messages = [
            {"role": "system", "content": quality_control_prompt},
            {"role": "user", "content": f"Please review and refine this EWA analysis JSON:\n\n{json.dumps(draft_json, indent=2)}"}
        ]
        
        response = await self._async_openai(messages)
        return json.loads(response.choices[0].message.function_call.arguments)

    async def _call_openai(self, markdown: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": self.summary_prompt},
            {"role": "user", "content": markdown},
        ]
        response = await self._async_openai(messages)
        return json.loads(response.choices[0].message.function_call.arguments)

    async def _repair(self, markdown: str, previous_json: Dict[str, Any]) -> Dict[str, Any]:
        repair_prompt = "The JSON you produced did not validate against the schema. Fix the issues and return ONLY the corrected JSON object."
        messages = [
            {"role": "system", "content": self.summary_prompt},
            {"role": "assistant", "content": json.dumps(previous_json)},
            {"role": "user", "content": repair_prompt},
        ]
        response = await self._async_openai(messages)
        return json.loads(response.choices[0].message.function_call.arguments)

    async def _async_openai(self, messages):
        loop = asyncio.get_running_loop()
        def call():
            if any(x in self.model for x in ["o4-mini", "o3"]):
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_completion_tokens=32768,
                    reasoning_effort="high",
                    functions=[self.function_def],
                    function_call={"name": "create_ewa_summary"},
                )
            else:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=16384,
                    functions=[self.function_def],
                    function_call={"name": "create_ewa_summary"},
                    temperature=0.0,
                )
        import traceback
        try:
            response = await loop.run_in_executor(None, call)
            # Print token usage if available
            if hasattr(response, 'usage') and response.usage is not None:
                prompt_tokens = getattr(response.usage, 'prompt_tokens', None)
                completion_tokens = getattr(response.usage, 'completion_tokens', None)
                total_tokens = getattr(response.usage, 'total_tokens', None)
                print(f"[TOKEN USAGE] Prompt: {prompt_tokens} | Completion: {completion_tokens} | Total: {total_tokens}")
            return response
        except Exception as e:
            print("[EWAAgent._async_openai] Exception occurred:")
            traceback.print_exc()
            raise

    def _is_valid(self, data: Dict[str, Any]) -> bool:
        try:
            validate(instance=data, schema=self.schema)
            return True
        except ValidationError:
            return False
