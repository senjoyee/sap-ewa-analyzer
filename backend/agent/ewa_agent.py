"""Agent responsible for producing a structured JSON summary for an SAP EWA report using Azure OpenAI or Google Gemini."""
from __future__ import annotations

import os
import json
import asyncio
import tempfile
import copy
from typing import Dict, Any, Union
from jsonschema import validate, ValidationError
from models.gemini_client import GeminiClient, is_gemini_model
from utils.json_repair import JSONRepair

# Note: LLM-based JSON repair has been removed.
# EWAAgent uses local deterministic repair via utils.json_repair.JSONRepair.

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
        
        # Local JSON repair utility (non-LLM)
        self.json_repair = JSONRepair()

    # ----------------------------- Public API ----------------------------- #
    async def run(self, markdown: str, pdf_data: bytes = None) -> Dict[str, Any]:
        """Return a validated summary JSON object.
        Attempts a single local (non-LLM) repair if initial output is invalid.
        """
        summary_json = await self._call_llm(markdown, pdf_data)
        if self._is_valid(summary_json):
            print("[EWAAgent.run] Initial JSON valid; skipping repair")
            return summary_json

        # Try local repair (no LLM)
        print("[EWAAgent.run] Initial JSON invalid; invoking local JSON repair")
        summary_json = self._repair_local(markdown, summary_json)
        # Log result validity (return value unchanged)
        try:
            is_valid_after = self._is_valid(summary_json)
            print(f"[EWAAgent.run] Local repair completed; valid={is_valid_after}")
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
        """Use Azure OpenAI Responses API with Structured Outputs via text.format and optional PDF input.
        Returns the parsed JSON directly when available; otherwise falls back to output_text parsing/repair.
        """

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
                    # Offload blocking Files API upload to a thread
                    uploaded = await asyncio.to_thread(lambda: self.client.files.create(file=file_obj, purpose="assistants"))
                    file_id = uploaded.id
                finally:
                    file_obj.close()

            instruction_text = (
                f"{self.summary_prompt}\n\n"
                "Return ONLY a valid JSON object that strictly conforms to the provided JSON schema. "
                "Do not include any text outside of the JSON. Use double-quoted keys and strings, no trailing commas, and no comments. "
                "Emit ONLY keys defined by the schema (treat additionalProperties as false across all objects) — do not add any extra properties anywhere. "
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

            # Prepare a STRICT schema for Structured Outputs by forcing additionalProperties: false on all objects
            strict_schema = self._make_strict_schema_for_structured_outputs(self.schema)

            # Structured outputs: provide the JSON schema using text.format (compatible shape)
            text_format = {
                "format": {
                    "type": "json_schema",
                    "name": self.function_def["name"],
                    "schema": strict_schema,
                    "strict": True,
                },
                "verbosity": "high",
            }

            # Single-path call using text.format; offload blocking call to a thread
            response = await asyncio.to_thread(
                lambda: self.client.responses.create(
                    model=self.model,
                    input=[{"role": "user", "content": user_content}],
                    text=text_format,
                    max_output_tokens=16384,
                    reasoning={"effort": "medium"},
                )
            )
            # Log token usage for visibility
            try:
                usage = getattr(response, "usage", None)
                in_tok = out_tok = None
                if usage is not None:
                    # usage may be a pydantic model or dict
                    in_tok = getattr(usage, "input_tokens", None) if hasattr(usage, "input_tokens") else (usage.get("input_tokens") if isinstance(usage, dict) else None)
                    out_tok = getattr(usage, "output_tokens", None) if hasattr(usage, "output_tokens") else (usage.get("output_tokens") if isinstance(usage, dict) else None)
                if in_tok is None or out_tok is None:
                    try:
                        resp_dict = response.model_dump() if hasattr(response, "model_dump") else None
                        if isinstance(resp_dict, dict):
                            u = resp_dict.get("usage", {})
                            if in_tok is None:
                                in_tok = u.get("input_tokens")
                            if out_tok is None:
                                out_tok = u.get("output_tokens")
                    except Exception:
                        pass
                print(f"[EWAAgent._call_openai_responses] Token usage: input_tokens={in_tok}, output_tokens={out_tok}")
            except Exception:
                # Do not fail if usage is unavailable
                pass

            # Extract structured output
            try:
                parsed = getattr(response, "output_parsed", None)
                if parsed is not None:
                    if isinstance(parsed, dict):
                        return parsed
                    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                        data0 = parsed[0]
                        return data0
            except Exception:
                pass

            # Fallback to output_text and parse/repair
            text = getattr(response, "output_text", None)
            if text:
                try:
                    data = json.loads(text)
                    return data
                except Exception:
                    try:
                        rr = self.json_repair.repair(text)
                        if rr.success and isinstance(rr.data, dict):
                            return rr.data
                    except Exception:
                        pass
                    # As last resort, return sentinel to allow _repair_local() in run()
                    return {"_parse_error": "Failed to parse structured output", "raw_arguments": text[:50000]}

            # If neither parsed nor text available, dump raw for debugging and return empty result
            print("[EWAAgent._call_openai_responses] No output_parsed or output_text; raw response:")
            try:
                print(response.model_dump_json(indent=2))
            except Exception:
                print(str(response))
            return {"_parse_error": "No output returned", "raw_arguments": ""}
        finally:
            # Cleanup any temp file created
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def _make_strict_schema_for_structured_outputs(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Return a deep-copied schema where every object has additionalProperties set to False.
        This aligns with Structured Outputs strict-mode requirements.
        """
        def visit(node: Any) -> Any:
            if isinstance(node, dict):
                t = node.get("type")
                if t == "object":
                    # Explicitly disallow additional properties for strict schema enforcement
                    node["additionalProperties"] = False
                    props = node.get("properties")
                    if isinstance(props, dict):
                        for k, v in props.items():
                            props[k] = visit(v)
                    pat = node.get("patternProperties")
                    if isinstance(pat, dict):
                        for k, v in pat.items():
                            pat[k] = visit(v)
                # Recurse into array items
                items = node.get("items")
                if isinstance(items, dict):
                    node["items"] = visit(items)
                elif isinstance(items, list):
                    node["items"] = [visit(it) for it in items]
                # Recurse into combinators if present
                for key in ("allOf", "anyOf", "oneOf"):
                    seq = node.get(key)
                    if isinstance(seq, list):
                        node[key] = [visit(s) for s in seq]
                return node
            elif isinstance(node, list):
                return [visit(n) for n in node]
            else:
                return node

        copy_schema = copy.deepcopy(schema)
        return visit(copy_schema)

    
    
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

    def _repair_local(self, markdown: str, previous_json: Dict[str, Any]) -> Dict[str, Any]:
        """Repair JSON locally without LLM calls. This is the only repair path.
        - If we have raw_arguments (string) from a failed parse, repair that.
        - Otherwise, attempt to repair the serialized previous_json.
        Returns the repaired dict on success, else the original previous_json.
        """
        try:
            # If parse previously failed and we captured raw arguments, try repairing that string first
            if isinstance(previous_json, dict) and "raw_arguments" in previous_json:
                raw = previous_json.get("raw_arguments", "")
                rr = self.json_repair.repair(raw)
                if rr.success and isinstance(rr.data, dict):
                    return rr.data

            # Otherwise, try repairing the JSON dump of the previous object
            text = json.dumps(previous_json, ensure_ascii=False)
            rr = self.json_repair.repair(text)
            if rr.success and isinstance(rr.data, dict):
                return rr.data
        except Exception as e:
            print(f"[EWAAgent._repair_local] Exception during local repair: {e}")
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
            # Attempt local repair on the raw arguments string
            try:
                rr = self.json_repair.repair(args_str)
                if rr.success and isinstance(rr.data, dict):
                    return rr.data
            except Exception:
                pass
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
