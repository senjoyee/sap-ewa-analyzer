"""Agent responsible for producing a structured JSON summary for an SAP EWA report using Azure OpenAI or Google Gemini."""
from __future__ import annotations

import os
import json
import asyncio
import tempfile
from typing import Dict, Any, Union
from jsonschema import validate, ValidationError
from models.gemini_client import GeminiClient, is_gemini_model

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

# Directory containing prompt templates
_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts")
_OPENAI_PROMPT_PATH = os.path.join(_PROMPT_DIR, "ewa_summary_prompt_openai.md")
_GEMINI_PROMPT_PATH = os.path.join(_PROMPT_DIR, "ewa_summary_prompt_openai_google.md")
_OPENAI_GPT5_PROMPT_PATH = os.path.join(_PROMPT_DIR, "ewa_summary_prompt_openai_gpt5.md")

# Fallback: if specific prompt files are unavailable, use inline DEFAULT_PROMPT above
_DEFAULT_FALLBACK_PROMPT_PATH = _OPENAI_PROMPT_PATH  # prefer OpenAI template for fallback
if os.path.exists(_DEFAULT_FALLBACK_PROMPT_PATH):
    with open(_DEFAULT_FALLBACK_PROMPT_PATH, "r", encoding="utf-8") as _f:
        DEFAULT_PROMPT = _f.read()

class EWAAgent:
    """Small agent that plans (single step) and returns a validated JSON summary."""

    def __init__(self, client: Union[object, GeminiClient, None], model: str, summary_prompt: str | None = None, schema_path: str | None = None):
        self.client = client
        self.model = model
        # Determine model type and load appropriate prompt
        self.is_gemini = is_gemini_model(model)

        if summary_prompt is not None:
            self.summary_prompt = summary_prompt
        else:
            # Select prompt file based on model
            if self.is_gemini:
                candidate_paths = [
                    _GEMINI_PROMPT_PATH,
                    _OPENAI_GPT5_PROMPT_PATH,  # fallback to GPT-5 optimized if present
                    _OPENAI_PROMPT_PATH,
                ]
            else:
                model_lc = (self.model or "").lower()
                if "gpt-5" in model_lc:
                    candidate_paths = [
                        _OPENAI_GPT5_PROMPT_PATH,  # preferred for GPT-5 family
                        _OPENAI_PROMPT_PATH,
                        _GEMINI_PROMPT_PATH,
                    ]
                else:
                    candidate_paths = [
                        _OPENAI_PROMPT_PATH,
                        _OPENAI_GPT5_PROMPT_PATH,
                        _GEMINI_PROMPT_PATH,
                    ]

            loaded = None
            for p in candidate_paths:
                if os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8") as _p:
                            loaded = _p.read()
                            print(f"[EWAAgent] Loaded summary prompt from {p}")
                            break
                    except Exception as e:
                        print(f"[EWAAgent] Warning: Could not read prompt file {p}: {e}")
                        continue
            self.summary_prompt = loaded if loaded is not None else DEFAULT_PROMPT

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
    async def run(self, markdown: str, pdf_data: bytes = None) -> Dict[str, Any]:
        """Return a validated summary JSON object. May attempt a single self-repair."""
        summary_json = await self._call_llm(markdown, pdf_data)
        if self._is_valid(summary_json):
            print("[EWAAgent.run] Initial JSON valid; skipping repair")
            return summary_json

        # Try once to repair
        print(f"[EWAAgent.run] Initial JSON invalid; invoking repair via {'Gemini' if self.is_gemini else 'OpenAI'}")
        summary_json = await self._repair(markdown, summary_json, pdf_data)
        # Log result validity (return value unchanged)
        try:
            is_valid_after = self._is_valid(summary_json)
            print(f"[EWAAgent.run] Repair completed; valid={is_valid_after}")
        except Exception:
            # Be resilient to unexpected types
            print("[EWAAgent.run] Repair completed; validity check raised an exception")
        return summary_json
    

    # ----------------------------- Internal helpers ----------------------------- #


    async def _call_llm(self, markdown: str, pdf_data: bytes = None) -> Dict[str, Any]:
        """Call either OpenAI or Gemini based on model type"""
        if self.is_gemini:
            return await self._call_gemini(markdown, pdf_data)
        else:
            # Use Responses API with optional PDF input for OpenAI path
            return await self._call_openai_responses(markdown, pdf_data)
    

    async def _call_openai_responses(self, markdown: str, pdf_data: bytes | None) -> Dict[str, Any]:
        """Use Azure OpenAI Responses API with function-calling and optional PDF input.
        Returns the parsed JSON from the function call arguments.
        """
        # Prepare tool (function) definition using the existing JSON schema
        tools = [
            {
                "type": "function",
                "name": self.function_def["name"],
                "description": self.function_def["description"],
                "parameters": self.function_def["parameters"],
            }
        ]

        # Build input content
        user_content = []

        file_id = None
        temp_path = None
        try:
            if pdf_data:
                # Upload PDF bytes as a temp file to Files API (purpose="assistants")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(pdf_data)
                    temp_path = tmp.name
                file_obj = open(temp_path, "rb")
                try:
                    uploaded = self.client.files.create(file=file_obj, purpose="assistants")
                    file_id = uploaded.id
                finally:
                    file_obj.close()

            instruction_text = (
                f"{self.summary_prompt}\n\n"
                "Return ONLY a function call to create_ewa_summary with arguments containing the final JSON. "
                "The function call arguments MUST be strictly valid JSON (RFC 8259): use double-quoted keys and strings, no trailing commas, no comments, and no extra text outside JSON."
            )

            if file_id:
                user_content.append({"type": "input_file", "file_id": file_id})
                user_content.append({"type": "input_text", "text": "Please analyze the attached EWA PDF and produce the structured JSON."})
            else:
                # Use markdown input
                user_content.append({"type": "input_text", "text": f"{instruction_text}\n\nAnalyze this EWA markdown document:\n\n{markdown}"})

            # If file was attached, include instructions as separate text to steer the function call
            if file_id:
                user_content.append({"type": "input_text", "text": instruction_text})

            response = self.client.responses.create(
                model=self.model,
                tools=tools,
                tool_choice={"type": "function", "name": self.function_def["name"]},
                input=[{"role": "user", "content": user_content}],
                max_output_tokens=16384,
                reasoning={"effort": "low"},
            )

            # Extract function_call arguments from the Responses output
            args_str = None
            try:
                for output_item in getattr(response, "output", []) or []:
                    # Expect a function_call item
                    if getattr(output_item, "type", None) == "function_call":
                        # output_item.arguments may already be a str
                        args_str = getattr(output_item, "arguments", None)
                        if args_str:
                            break
                if args_str is None:
                    # As a fallback, try output_text (may be empty with forced tool_choice)
                    text = getattr(response, "output_text", None)
                    if text:
                        args_str = text
            except Exception:
                # In case of SDK shape changes, dump the raw response for debugging
                print("[EWAAgent._call_openai_responses] Unable to parse response.output; raw:")
                try:
                    print(response.model_dump_json(indent=2))
                except Exception:
                    print(str(response))
                raise

            # Extract and parse arguments to JSON
            try:
                return self._parse_json_arguments(args_str)
            except Exception as e:
                print(f"[EWAAgent._call_openai_responses] JSON parse failed; will trigger repair via run(): {e}")
                # Return sentinel dict to force repair in run(); also include raw arguments for debugging/repair prompt
                raw = args_str if isinstance(args_str, str) else str(args_str)
                return {"_parse_error": str(e), "raw_arguments": raw[:50000]}
        finally:
            # Cleanup any temp file created
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
    
    async def _call_gemini(self, markdown: str, pdf_data: bytes = None) -> Dict[str, Any]:
        """Call Gemini API for JSON generation with optional PDF input"""
        try:
            # Add JSON schema to the prompt for Gemini
            schema_instruction = f"\n\nIMPORTANT: Your response must conform to this exact JSON schema:\n{json.dumps(self.schema, indent=2)}"
            enhanced_prompt = self.summary_prompt + schema_instruction
            
            # Modify prompt based on input type
            if pdf_data:
                input_prompt = "Please analyze the attached PDF document and provide a comprehensive EWA analysis."
                print(f"[Gemini] Using PDF input ({len(pdf_data)} bytes) instead of markdown")
            else:
                input_prompt = markdown
                print(f"[Gemini] Using markdown input ({len(markdown)} characters)")
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.client.generate_json_content(input_prompt, enhanced_prompt, pdf_data)
            )
            
            return response
            
        except Exception as e:
            print(f"[EWAAgent._call_gemini] Exception occurred: {str(e)}")
            raise

    async def _repair(self, markdown: str, previous_json: Dict[str, Any], pdf_data: bytes = None) -> Dict[str, Any]:
        """Repair invalid JSON response"""
        if self.is_gemini:
            return await self._repair_gemini(markdown, previous_json, pdf_data)
        else:
            return await self._repair_openai(markdown, previous_json, pdf_data)
    
    async def _repair_openai(self, markdown: str, previous_json: Dict[str, Any], pdf_data: bytes | None) -> Dict[str, Any]:
        """Use Responses API to repair invalid JSON by forcing a function call again."""
        print("[EWAAgent._repair_openai] Invoked (Responses API)")
        tools = [
            {
                "type": "function",
                "name": self.function_def["name"],
                "description": self.function_def["description"],
                "parameters": self.function_def["parameters"],
            }
        ]

        repair_instruction = (
            "The previous JSON did not validate against the schema. Fix all validation errors and return ONLY the corrected JSON via the function call arguments. "
            "Your function call arguments MUST be strictly valid JSON (RFC 8259): double-quoted keys and strings, no trailing commas, no comments, and no extra text outside JSON."
        )

        content_items = []
        if pdf_data:
            # Prefer reusing the PDF context again when available
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_data)
                temp_path = tmp.name
            file_obj = open(temp_path, "rb")
            try:
                uploaded = self.client.files.create(file=file_obj, purpose="assistants")
                file_id = uploaded.id
            finally:
                file_obj.close()
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            content_items.append({"type": "input_file", "file_id": file_id})

        content_items.append({"type": "input_text", "text": self.summary_prompt})
        # Provide both the invalid JSON and (if no PDF) the original markdown for context
        if not pdf_data:
            content_items.append({"type": "input_text", "text": f"Original markdown content:\n\n{markdown}"})
        content_items.append({"type": "input_text", "text": f"Invalid JSON response to repair:\n\n{json.dumps(previous_json, indent=2)}"})
        content_items.append({"type": "input_text", "text": repair_instruction})

        response = self.client.responses.create(
            model=self.model,
            tools=tools,
            tool_choice={"type": "function", "name": self.function_def["name"]},
            input=[{"role": "user", "content": content_items}],
            max_output_tokens=16384,
            reasoning={"effort": "low"},
        )

        # Extract and parse arguments
        args_str = None
        for output_item in getattr(response, "output", []) or []:
            if getattr(output_item, "type", None) == "function_call":
                args_str = getattr(output_item, "arguments", None)
                if args_str:
                    break
        if not args_str:
            # As a fallback, try output_text
            text = getattr(response, "output_text", None)
            if text:
                args_str = text
        if not args_str:
            # If still nothing, return previous_json as a last resort
            print("[EWAAgent._repair_openai] No function_call arguments returned; returning previous JSON")
            return previous_json
        return self._parse_json_arguments(args_str)
    
    async def _repair_gemini(self, markdown: str, previous_json: Dict[str, Any], pdf_data: bytes = None) -> Dict[str, Any]:
        """Repair JSON using Gemini with optional PDF input"""
        print("[EWAAgent._repair_gemini] Invoked")
        try:
            if pdf_data:
                repair_prompt = f"""The following JSON response did not validate against the required schema. Please fix all validation errors and return ONLY the corrected JSON object.

Analyze the attached PDF document and correct the JSON response.

Invalid JSON response:
{json.dumps(previous_json, indent=2)}

Required JSON schema:
{json.dumps(self.schema, indent=2)}

Please analyze the validation errors and return the corrected JSON that conforms to the schema."""
            else:
                repair_prompt = f"""The following JSON response did not validate against the required schema. Please fix all validation errors and return ONLY the corrected JSON object.

Original markdown content:
{markdown}

Invalid JSON response:
{json.dumps(previous_json, indent=2)}

Required JSON schema:
{json.dumps(self.schema, indent=2)}

Please analyze the validation errors and return the corrected JSON that conforms to the schema."""
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.client.generate_json_content(repair_prompt, pdf_data=pdf_data)
            )
            
            return response
            
        except Exception as e:
            print(f"[EWAAgent._repair_gemini] Exception occurred: {str(e)}")
            # Return the original response if repair fails
            return previous_json

    

    def _is_valid(self, data: Dict[str, Any]) -> bool:
        try:
            validate(instance=data, schema=self.schema)
            return True
        except ValidationError:
            return False

    def _parse_json_arguments(self, args_str: Any) -> Dict[str, Any]:
        """Parse JSON from a function_call.arguments string.
        Be resilient to minor formatting issues (e.g., code fences).
        """
        if isinstance(args_str, dict):
            return args_str
        if not isinstance(args_str, str):
            raise ValueError("Function call arguments are not a string or dict")
        try:
            return json.loads(args_str)
        except Exception:
            # Strip code fences or extract JSON substring
            start = args_str.find('{')
            end = args_str.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = args_str[start:end+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    pass
            # Last resort
            raise
