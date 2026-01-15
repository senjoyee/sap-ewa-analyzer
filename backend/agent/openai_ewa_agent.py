"""Agent responsible for producing a structured JSON summary for an SAP EWA report using Azure OpenAI."""
from __future__ import annotations

import os
import json
import asyncio
import tempfile
import copy
from typing import Dict, Any, Union
from jsonschema import validate, ValidationError
from utils.json_repair import JSONRepair

# Note: LLM-based JSON repair has been removed.
# OpenAIEWAAgent uses local deterministic repair via utils.json_repair.JSONRepair.

# Directory containing prompt templates
_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts")
_OPENAI_PROMPT_PATH = os.path.join(_PROMPT_DIR, "ewa_summary_prompt_openai.md")


class OpenAIEWAAgent:
    """Small agent that plans (single step) and returns a validated JSON summary."""

    def __init__(self, client: Union[object, None], model: str, summary_prompt: str | None = None, schema_path: str | None = None):
        self.client = client
        self.model = model

        if summary_prompt is not None:
            self.summary_prompt = summary_prompt
        else:
            candidate_paths = [_OPENAI_PROMPT_PATH]

            loaded = None
            for p in candidate_paths:
                if os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8") as _p:
                            loaded = _p.read()
                            print(f"[OpenAIEWAAgent] Loaded summary prompt from {p}")
                            break
                    except Exception as e:
                        print(f"[OpenAIEWAAgent] Warning: Could not read prompt file {p}: {e}")
                        continue
            if loaded is None:
                raise FileNotFoundError(
                    f"No prompt file found. Expected one of: {candidate_paths}"
                )
            self.summary_prompt = loaded

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
        summary_json = await self._call_openai_responses(markdown, pdf_data)
        if self._is_valid(summary_json):
            print("[OpenAIEWAAgent.run] Initial JSON valid; skipping repair")
            return summary_json

        # Try local repair (no LLM)
        print("[OpenAIEWAAgent.run] Initial JSON invalid; invoking local JSON repair")
        summary_json = self._repair_local(markdown, summary_json)
        # Log result validity (return value unchanged)
        try:
            is_valid_after = self._is_valid(summary_json)
            print(f"[OpenAIEWAAgent.run] Local repair completed; valid={is_valid_after}")
        except Exception:
            # Be resilient to unexpected types
            print("[OpenAIEWAAgent.run] Repair completed; validity check raised an exception")
        return summary_json
    

    # ----------------------------- Internal helpers ----------------------------- #


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
                # If file was attached, include instructions as separate text to steer the function call
                user_content.append({"type": "input_text", "text": instruction_text})
            else:
                # Use markdown input with Prompt Caching strategy:
                # 1. Document content first (large static prefix)
                # 2. Instructions second
                user_content.append({"type": "input_text", "text": markdown})
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
                # "verbosity": "high",  # use default verbosity
            }

            # Single-path call using text.format; offload blocking call to a thread
            response = await asyncio.to_thread(
                lambda: self.client.responses.create(
                    model=self.model,
                    input=[{"role": "user", "content": user_content}],
                    text=text_format,
                    max_output_tokens=32768,
                    # reasoning={"effort": "medium"},  # use default reasoning effort
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
                print(f"[OpenAIEWAAgent._call_openai_responses] Token usage: input_tokens={in_tok}, output_tokens={out_tok}")
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
            print("[OpenAIEWAAgent._call_openai_responses] No output_parsed or output_text; raw response:")
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
            print(f"[OpenAIEWAAgent._repair_local] Exception during local repair: {e}")
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
