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
    async def run(self, markdown: str, previous_kpis: List[Dict] = None, canonical_kpi_names: List[str] = None) -> Dict[str, Any]:
        """Return a validated summary JSON object. May attempt a single self-repair."""
        # Modify the prompt to include previous KPI data and canonical KPI names
        enhanced_prompt = self.summary_prompt
        
        if previous_kpis:
            enhanced_prompt += f"\n\nPrevious KPI data for trend analysis:\n{json.dumps(previous_kpis, indent=2)}"
        
        if canonical_kpi_names:
            enhanced_prompt += f"\n\nCanonical KPI names (you MUST use only these names):\n{json.dumps(canonical_kpi_names, indent=2)}"
        
        summary_json = await self._call_openai(markdown, enhanced_prompt)
        if self._is_valid(summary_json):
            return summary_json

        # Try once to repair
        summary_json = await self._repair(markdown, summary_json, enhanced_prompt)
        # Either returns valid JSON or last attempt regardless of validity
        return summary_json
    

    # ----------------------------- Internal helpers ----------------------------- #


    async def _call_openai(self, markdown: str, enhanced_prompt: str = None) -> Dict[str, Any]:
        prompt_to_use = enhanced_prompt if enhanced_prompt is not None else self.summary_prompt
        messages = [
            {"role": "system", "content": prompt_to_use},
            {"role": "user", "content": markdown},
        ]
        response = await self._async_openai(messages)
        return json.loads(response.choices[0].message.function_call.arguments)

    async def _repair(self, markdown: str, previous_json: Dict[str, Any], enhanced_prompt: str = None) -> Dict[str, Any]:
        prompt_to_use = enhanced_prompt if enhanced_prompt is not None else self.summary_prompt
        repair_prompt = "The JSON you produced did not validate against the schema. Fix the issues and return ONLY the corrected JSON object."
        messages = [
            {"role": "system", "content": prompt_to_use},
            {"role": "assistant", "content": json.dumps(previous_json)},
            {"role": "user", "content": repair_prompt},
        ]
        response = await self._async_openai(messages)
        return json.loads(response.choices[0].message.function_call.arguments)

    async def _async_openai(self, messages):
        loop = asyncio.get_running_loop()
        def call():
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
