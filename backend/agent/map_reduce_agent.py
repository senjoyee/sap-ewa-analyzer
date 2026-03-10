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

AREA_ORDER = {
    "sap hana": 0,
    "database": 1,
    "sap kernel": 2,
    "profile parameters": 3,
    "application": 4,
    "memory/buffer": 5,
    "operating system": 6,
    "network": 7,
    "general": 8,
}

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

INVENTORY_PARAMETER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"^database system$",
        r"^database version$",
        r"^db id$",
        r"^db host$",
        r"^sapdbhost$",
        r"^sap product$",
        r"^product version$",
        r"^sap hana database version$",
        r"^sap s/4hana release$",
        r"^hardware manufacturer\\b",
        r"^model\\b",
        r"^cpu type\\b",
        r"^cpu mhz\\b",
        r"^operating system\\b",
        r"^cpus\\b",
        r"^cores\\b",
        r"^memory\\b",
    ]
]

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
        # Extract the inner 'schema' if the dictionary is wrapped for Structured Outputs
        self.schema = schema_dict.get("schema", schema_dict) if isinstance(schema_dict, dict) else schema_dict
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


    def _normalize_text(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()


    def _completeness_score(self, item: Dict[str, Any], fields: List[str]) -> int:
        score = 0
        for field in fields:
            value = self._normalize_text(item.get(field, ""))
            if value:
                score += 1
        return score


    def _is_chapter_one_overview(self, title_line: str) -> bool:
        normalized = title_line.lower()
        return (" 1." in normalized or "# 1 " in normalized) and "overview" in normalized


    def _extract_chapter_items(self, markdown: str) -> List[Dict[str, str]]:
        """Extract chapter titles and text chunks from the markdown in source order."""
        pattern = re.compile(r'^(# \d+\.? .*$)', re.MULTILINE)
        matches = list(pattern.finditer(markdown))

        if not matches:
            text = markdown.strip()
            if not text:
                return []
            logger.warning("No chapter headers found in markdown. Returning whole file as one chunk.")
            return [{"title": "Document", "text": text}]

        items: List[Dict[str, str]] = []
        for i in range(len(matches)):
            start_idx = matches[i].start()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            chunk_text = markdown[start_idx:end_idx].strip()
            raw_title = matches[i].group(1).strip()

            if self._is_chapter_one_overview(raw_title):
                logger.info("Skipping Chapter 1: %s", raw_title)
                continue

            if len(chunk_text) <= 50:
                continue

            title = re.sub(r'^#\s*\d+\.?\s*', '', raw_title).strip()
            items.append({"title": title or raw_title.lstrip("# ").strip(), "text": chunk_text})

        logger.info("Split document into %d chapters for Map phase.", len(items))
        return items


    def _normalize_chapters(self, chapter_titles: List[str]) -> List[str]:
        normalized_titles: List[str] = []
        seen = set()
        for title in chapter_titles:
            clean_title = self._normalize_text(title)
            if not clean_title:
                continue
            key = clean_title.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized_titles.append(clean_title)
        return normalized_titles


    def _normalize_positive_findings(self, findings: Any) -> List[Dict[str, str]]:
        if not isinstance(findings, list):
            return []

        deduped: Dict[tuple[str, str], Dict[str, str]] = {}
        for item in findings:
            if not isinstance(item, dict):
                continue
            area = self._normalize_text(item.get("Area") or item.get("area") or "General") or "General"
            description = self._normalize_text(item.get("Description") or item.get("description") or "")
            if not description or description.lower() in {"none", "n/a"}:
                continue

            key = (area.lower(), description.lower())
            deduped[key] = {"Area": area, "Description": description}

        return sorted(
            deduped.values(),
            key=lambda item: (
                self._normalize_text(item.get("Area", "")).lower(),
                self._normalize_text(item.get("Description", "")).lower(),
            ),
        )


    def _looks_like_inventory_parameter(self, parameter_name: str, recommended_value: str, action_status: str) -> bool:
        if recommended_value or action_status in {"Change Required", "Verify", "Monitor"}:
            return False
        name = self._normalize_text(parameter_name)
        if not name:
            return True
        return any(pattern.search(name) for pattern in INVENTORY_PARAMETER_PATTERNS)


    def _normalize_technical_parameters(self, parameters: Any) -> List[Dict[str, str]]:
        if not isinstance(parameters, list):
            return []

        deduped: Dict[tuple[str, str], Dict[str, str]] = {}
        for param in parameters:
            if not isinstance(param, dict):
                continue

            parameter_name = self._normalize_text(param.get("parameter_name"))
            if not parameter_name:
                continue

            area = self._normalize_text(param.get("area") or "General") or "General"
            current_value = self._normalize_text(param.get("current_value"))
            recommended_value = self._normalize_text(param.get("recommended_value"))
            action_status = self._normalize_text(param.get("action_status") or "No Action") or "No Action"
            priority = self._normalize_text(param.get("priority") or "Low") or "Low"
            description = self._normalize_text(param.get("description"))
            source_section = self._normalize_text(param.get("source_section") or param.get("section"))

            if self._looks_like_inventory_parameter(parameter_name, recommended_value, action_status):
                continue

            normalized_param = {
                "parameter_name": parameter_name,
                "area": area,
                "current_value": current_value,
                "recommended_value": recommended_value,
                "action_status": action_status,
                "priority": priority,
                "description": description,
                "source_section": source_section,
            }

            dedupe_key = (parameter_name.lower(), area.lower())
            existing = deduped.get(dedupe_key)
            if existing is None:
                deduped[dedupe_key] = normalized_param
                continue

            existing_score = self._completeness_score(existing, [
                "current_value", "recommended_value", "description", "source_section"
            ])
            candidate_score = self._completeness_score(normalized_param, [
                "current_value", "recommended_value", "description", "source_section"
            ])
            if normalized_param["action_status"] != "No Action":
                candidate_score += 2
            if existing["action_status"] != "No Action":
                existing_score += 2

            if candidate_score > existing_score:
                deduped[dedupe_key] = normalized_param

        return sorted(
            deduped.values(),
            key=lambda item: (
                AREA_ORDER.get(self._normalize_text(item.get("area", "")).lower(), 999),
                self._normalize_text(item.get("parameter_name", "")).lower(),
                self._normalize_text(item.get("source_section", "")).lower(),
            ),
        )


    def _normalize_findings_and_recommendations(
        self,
        findings: Any,
        recommendations: Any,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        normalized_findings_input = findings if isinstance(findings, list) else []
        normalized_recommendations_input = recommendations if isinstance(recommendations, list) else []

        deduped_findings: Dict[tuple[str, str], Dict[str, Any]] = {}
        original_to_new_ids: Dict[str, str] = {}

        for finding in normalized_findings_input:
            if not isinstance(finding, dict):
                continue
            area = self._normalize_text(finding.get("Area") or finding.get("area"))
            finding_text = self._normalize_text(finding.get("Finding") or finding.get("finding"))
            if not area or not finding_text:
                continue

            severity = self._normalize_text(finding.get("Severity") or finding.get("severity") or "medium").lower() or "medium"
            if severity not in SEVERITY_ORDER:
                severity = "medium"

            normalized_finding = {
                "Issue ID": self._normalize_text(finding.get("Issue ID") or finding.get("issue_id")),
                "Area": area,
                "Finding": finding_text,
                "Impact": self._normalize_text(finding.get("Impact") or finding.get("impact")),
                "Business impact": self._normalize_text(finding.get("Business impact") or finding.get("business_impact")),
                "Severity": severity,
                "Source": self._normalize_text(finding.get("Source") or finding.get("source")),
            }
            dedupe_key = (area.lower(), finding_text.lower())
            existing = deduped_findings.get(dedupe_key)
            if existing is None:
                deduped_findings[dedupe_key] = normalized_finding
                continue

            existing_score = self._completeness_score(existing, ["Impact", "Business impact", "Source"])
            candidate_score = self._completeness_score(normalized_finding, ["Impact", "Business impact", "Source"])
            if SEVERITY_ORDER[normalized_finding["Severity"]] < SEVERITY_ORDER[existing["Severity"]]:
                candidate_score += 2
            elif SEVERITY_ORDER[existing["Severity"]] < SEVERITY_ORDER[normalized_finding["Severity"]]:
                existing_score += 2
            if candidate_score > existing_score:
                deduped_findings[dedupe_key] = normalized_finding

        sorted_findings = sorted(
            deduped_findings.values(),
            key=lambda item: (
                SEVERITY_ORDER.get(self._normalize_text(item.get("Severity", "medium")).lower(), 999),
                self._normalize_text(item.get("Area", "")).lower(),
                self._normalize_text(item.get("Finding", "")).lower(),
            ),
        )

        final_findings: List[Dict[str, Any]] = []
        for index, finding in enumerate(sorted_findings, start=1):
            new_id = f"KF-{index:02d}"
            original_id = self._normalize_text(finding.get("Issue ID"))
            if original_id:
                original_to_new_ids[original_id] = new_id
            updated_finding = dict(finding)
            updated_finding["Issue ID"] = new_id
            final_findings.append(updated_finding)

        deduped_recommendations: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        for recommendation in normalized_recommendations_input:
            if not isinstance(recommendation, dict):
                continue

            linked_issue_id = self._normalize_text(
                recommendation.get("Linked issue ID") or recommendation.get("linked_issue_id")
            )
            if linked_issue_id in original_to_new_ids:
                linked_issue_id = original_to_new_ids[linked_issue_id]
            elif not re.match(r"^KF-\d{2}$", linked_issue_id):
                continue

            action = self._normalize_text(recommendation.get("Action") or recommendation.get("action"))
            preventative_action = self._normalize_text(
                recommendation.get("Preventative Action") or recommendation.get("preventative_action")
            )
            if not action and not preventative_action:
                continue

            effort = recommendation.get("Estimated Effort") or recommendation.get("estimated_effort") or {}
            if not isinstance(effort, dict):
                effort = {}

            normalized_recommendation = {
                "Recommendation ID": self._normalize_text(
                    recommendation.get("Recommendation ID") or recommendation.get("recommendation_id")
                ),
                "Estimated Effort": {
                    "analysis": self._normalize_text(effort.get("analysis") or "low") or "low",
                    "implementation": self._normalize_text(effort.get("implementation") or "low") or "low",
                },
                "Responsible Area": self._normalize_text(
                    recommendation.get("Responsible Area") or recommendation.get("responsible_area") or "SAP Basis Team"
                ) or "SAP Basis Team",
                "Linked issue ID": linked_issue_id,
                "Action": action,
                "Preventative Action": preventative_action,
            }

            dedupe_key = (linked_issue_id.lower(), action.lower(), preventative_action.lower())
            existing = deduped_recommendations.get(dedupe_key)
            if existing is None:
                deduped_recommendations[dedupe_key] = normalized_recommendation
                continue

            existing_score = self._completeness_score(existing, ["Responsible Area", "Action", "Preventative Action"])
            candidate_score = self._completeness_score(normalized_recommendation, ["Responsible Area", "Action", "Preventative Action"])
            if candidate_score > existing_score:
                deduped_recommendations[dedupe_key] = normalized_recommendation

        sorted_recommendations = sorted(
            deduped_recommendations.values(),
            key=lambda item: (
                self._normalize_text(item.get("Linked issue ID", "")).lower(),
                self._normalize_text(item.get("Action", "")).lower(),
            ),
        )

        final_recommendations: List[Dict[str, Any]] = []
        for index, recommendation in enumerate(sorted_recommendations, start=1):
            updated_recommendation = dict(recommendation)
            updated_recommendation["Recommendation ID"] = f"REC-{index:02d}"
            final_recommendations.append(updated_recommendation)

        return final_findings, final_recommendations


    def _normalize_final_output(self, result: Dict[str, Any], chapter_titles: List[str]) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return result

        normalized_result = dict(result)
        normalized_result["Chapters Reviewed"] = self._normalize_chapters(chapter_titles)
        normalized_result["Positive Findings"] = self._normalize_positive_findings(
            normalized_result.get("Positive Findings", [])
        )
        normalized_result["Technical Parameters"] = self._normalize_technical_parameters(
            normalized_result.get("Technical Parameters", [])
        )
        findings, recommendations = self._normalize_findings_and_recommendations(
            normalized_result.get("Key Findings", []),
            normalized_result.get("Recommendations", []),
        )
        normalized_result["Key Findings"] = findings
        normalized_result["Recommendations"] = recommendations
        return normalized_result


    def _split_markdown_into_chapters(self, markdown: str) -> List[str]:
        """Slices the EWA markdown by top-level headers (# 1., # 2., etc.), ignoring Chapter 1.
        Limits chunks to a maximum length to prevent context explosion if formatting is weird.
        """
        return [item["text"] for item in self._extract_chapter_items(markdown)]

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
                    max_completion_tokens=2000,
                    temperature=0
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
                    input=[
                        sys_msg,
                        {"role": "user", "content": [{"type": "input_text", "text": user_msg["content"]}]}
                    ],
                    text=text_format,
                    temperature=0,
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

        chapter_items = self._extract_chapter_items(markdown)
        if not chapter_items:
            return {"_parse_error": "No chunks generated from markdown"}

        logger.info("Executing Map phase across %d chunks...", len(chapter_items))

        # Concurrently process all chunks
        map_tasks = [self._run_map_chunk(item["text"]) for item in chapter_items]
        mapped_notes = await asyncio.gather(*map_tasks)

        logger.info("Map phase completed. Executing Reduce phase...")

        # Run reduce on combined output
        json_output = await self._run_reduce(mapped_notes)
        json_output = self._normalize_final_output(
            json_output,
            [item["title"] for item in chapter_items],
        )

        logger.info("Map-Reduce workflow completed.")
        return json_output
