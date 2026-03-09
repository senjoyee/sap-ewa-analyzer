"""Agent implementing a Map-Reduce strategy for analyzing SAP EWA reports."""
import os
import re
import json
import asyncio
import copy
import logging
from typing import Dict, Any, List

from core.runtime_config import SUMMARY_MAX_OUTPUT_TOKENS, SUMMARY_REASONING_EFFORT

logger = logging.getLogger(__name__)

class MapReduceEWAAgent:
    """Agent that slices EWA reports, extracts detail in parallel (Map), and synthesizes a JSON summary (Reduce)."""

    def __init__(
        self, 
        client: Any, 
        map_model: str, 
        reduce_model: str, 
        map_prompt: str, 
        reduce_prompt: str, 
        schema_dict: Dict[str, Any]
    ):
        self.client = client
        self.map_model = map_model
        self.reduce_model = reduce_model
        self.map_prompt = map_prompt
        self.reduce_prompt = reduce_prompt
        self.schema = schema_dict
        self.last_usage: Dict[str, Any] = {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            "model": f"map:{self.map_model}, reduce:{self.reduce_model}",
            "reasoning_effort": SUMMARY_REASONING_EFFORT,
        }
        
    def _accumulate_usage(self, response: Any):
        """Helper to accumulate token usage from multiple API calls."""
        usage = getattr(response, "usage", None)
        if not usage:
            return

        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        elif not isinstance(usage, dict):
            usage = {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
                "input_tokens_details": getattr(usage, "input_tokens_details", None),
                "output_tokens_details": getattr(usage, "output_tokens_details", None),
            }

        input_details = (usage or {}).get("input_tokens_details") or {}
        output_details = (usage or {}).get("output_tokens_details") or {}

        if hasattr(input_details, "model_dump"):
            input_details = input_details.model_dump()
        elif not isinstance(input_details, dict):
            input_details = {"cached_tokens": getattr(input_details, "cached_tokens", 0)}

        if hasattr(output_details, "model_dump"):
            output_details = output_details.model_dump()
        elif not isinstance(output_details, dict):
            output_details = {"reasoning_tokens": getattr(output_details, "reasoning_tokens", 0)}

        self.last_usage["input_tokens"] += int((usage or {}).get("input_tokens") or 0)
        self.last_usage["output_tokens"] += int((usage or {}).get("output_tokens") or 0)
        self.last_usage["total_tokens"] += int((usage or {}).get("total_tokens") or 0)
        self.last_usage["cached_input_tokens"] += int(input_details.get("cached_tokens", 0) or 0)
        self.last_usage["reasoning_tokens"] += int(output_details.get("reasoning_tokens", 0) or 0)


    def _split_markdown_into_chapters(self, markdown: str) -> List[str]:
        """Slices the EWA markdown by top-level headers (# 1., # 2., etc.), ignoring Chapter 1.
        Limits chunks to a maximum length to prevent context explosion if formatting is weird.
        """
        # Split by top level headers roughly looking like "# 1. " or "# 2 "
        # We will use a regex to find all headers starting with "# " followed by digits.
        chunks = []
        
        # Regex to find top level headings that look like chapters: "# 1.", "# 2 ", etc.
        pattern = re.compile(r'^(# \d+\.? .*$)', re.MULTILINE)
        
        # Find all split points
        matches = list(pattern.finditer(markdown))
        
        if not matches:
            # Fallback: if no chapters found, chunk by length or just return the whole thing
            logger.warning("No chapter headers found in markdown. Returning whole file as one chunk.")
            return [markdown]
            
        # Extract chunks and their titles
        for i in range(len(matches)):
            start_idx = matches[i].start()
            end_idx = matches[i+1].start() if i + 1 < len(matches) else len(markdown)
            
            chunk_text = markdown[start_idx:end_idx].strip()
            title_line = matches[i].group(1).lower()
            
            # Skip chapter 1 (Check Overview or general intro), often just brief summaries
            if " 1." in title_line or "# 1 " in title_line:
                if "overview" in title_line:
                    logger.info("Skipping Chapter 1: %s", matches[i].group(1))
                    continue
            
            # If a chapter is too short, we could skip it, but let's process all for safety
            if len(chunk_text) > 50:
                chunks.append(chunk_text)
                
        logger.info("Split document into %d chapters for Map phase.", len(chunks))
        return chunks

    async def _run_map_chunk(self, chunk_text: str) -> str:
        """Runs the map prompt on a single text chunk."""
        user_content = [
            {"type": "input_text", "text": f"Analyze the following EWA chapter text:\n\n{chunk_text}"}
        ]
        
        try:
            # We use standard chat completions for the Map phase to get raw text output,
            # but since we are using gpt-5.x we use the unified responses completion or chat completion.
            # Using client.chat.completions.create mapping since it is simple plain text.
            response = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(
                    model=self.map_model,
                    messages=[
                        {"role": "system", "content": self.map_prompt},
                        {"role": "user", "content": chunk_text}
                    ],
                    max_tokens=2000,
                    temperature=0.1
                )
            )
            
            # Accumulate usage
            self._accumulate_usage(response)
            
            result_text = response.choices[0].message.content
            return result_text
        except Exception as e:
            logger.error("Error processing chunk: %s", str(e))
            return f"[Error processing chunk: {str(e)}]"

    def _make_strict_schema_for_structured_outputs(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Aligns the schema to Structured Outputs strict-mode requirements."""
        def visit(node: Any) -> Any:
            if isinstance(node, dict):
                t = node.get("type")
                if t == "object":
                    node["additionalProperties"] = False
                    props = node.get("properties")
                    if isinstance(props, dict):
                        for k, v in props.items():
                            props[k] = visit(v)
                items = node.get("items")
                if isinstance(items, dict):
                    node["items"] = visit(items)
                elif isinstance(items, list):
                    node["items"] = [visit(it) for it in items]
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

    async def _run_reduce(self, mapped_notes: List[str]) -> Dict[str, Any]:
        """Runs the Reduce phase using Structured Outputs."""
        
        combined_notes = "\n\n" + "="*50 + "\n\n".join(
            f"--- CHAPTER NOTES {i+1} ---\n{note}" for i, note in enumerate(mapped_notes)
        )
        
        strict_schema = self._make_strict_schema_for_structured_outputs(self.schema)
        
        text_format = {
            "format": {
                "type": "json_schema",
                "name": "create_executive_summary",
                "schema": strict_schema,
                "strict": True,
            }
        }
        
        sys_msg = {"role": "system", "content": self.reduce_prompt}
        user_msg = {
            "role": "user", 
            "content": f"Here are the combined notes from the Map phase. Please synthesize the final JSON structured report.\n<chapter_notes>\n{combined_notes}\n</chapter_notes>"
        }
        
        try:
            response = await asyncio.to_thread(
                lambda: self.client.responses.create(
                    model=self.reduce_model,
                    input=[sys_msg, {"role": "user", "content": [user_msg]}],
                    text=text_format,
                    reasoning={"effort": SUMMARY_REASONING_EFFORT},
                    max_output_tokens=SUMMARY_MAX_OUTPUT_TOKENS,
                )
            )
            
            self._accumulate_usage(response)
            
            # Safely extract
            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                    return parsed[0]
                    
            # Fallback text parsing
            text = getattr(response, "output_text", None)
            if text:
                try:
                    return json.loads(text)
                except Exception:
                    logger.error("Failed to parse json fallback in reduce.")
                    return {"_parse_error": "Failed to parse JSON string"}
            
            return {"_parse_error": "No output returned"}
            
        except Exception as e:
            logger.exception("Error during reduce phase: %s", e)
            return {"_parse_error": f"Exception in reduce: {str(e)}"}

    async def run(self, markdown: str) -> Dict[str, Any]:
        """Executes the full map-reduce pipeline on the given markdown."""
        logger.info("Starting Map-Reduce workflow.")
        
        chunks = self._split_markdown_into_chapters(markdown)
        if not chunks:
            return {"_parse_error": "No chunks generated from markdown"}
            
        logger.info("Executing Map phase across %d chunks...", len(chunks))
        
        # Concurrently process all chunks
        map_tasks = [self._run_map_chunk(chunk) for chunk in chunks]
        mapped_notes = await asyncio.gather(*map_tasks)
        
        logger.info("Map phase completed. Executing Reduce phase...")
        
        # Run reduce on combined output
        json_output = await self._run_reduce(mapped_notes)
        
        logger.info("Map-Reduce workflow completed.")
        return json_output
