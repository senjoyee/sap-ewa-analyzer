"""
Parameter Extraction Agent using GPT-5-mini for extracting SAP parameter recommendations.
Runs as a post-processing step after main EWA analysis to extract parameter changes from markdown.
"""
from __future__ import annotations

import os
import json
import asyncio
from typing import Dict, Any, List, Optional

# Action status values for parameter classification
ACTION_STATUS_CHANGE_REQUIRED = "Change Required"
ACTION_STATUS_VERIFY = "Verify"
ACTION_STATUS_NO_ACTION = "No Action"
ACTION_STATUS_MONITOR = "Monitor"

# Priority levels
PRIORITY_HIGH = "High"
PRIORITY_MEDIUM = "Medium"
PRIORITY_LOW = "Low"

# Schema for parameter extraction
PARAMETER_SCHEMA = {
    "type": "object",
    "properties": {
        "parameters": {
            "type": "array",
            "description": "List of all parameter information found in the document",
            "items": {
                "type": "object",
                "properties": {
                    "parameter_name": {
                        "type": "string",
                        "description": "The exact parameter name (e.g., rdisp/wp_no_dia, global_allocation_limit)"
                    },
                    "area": {
                        "type": "string",
                        "enum": ["SAP HANA", "Database", "SAP Kernel", "Profile Parameters", "Application", "Memory/Buffer", "Operating System", "Network", "General"],
                        "description": "The category/layer this parameter belongs to"
                    },
                    "current_value": {
                        "type": "string",
                        "description": "The current configured value (empty string if not specified)"
                    },
                    "recommended_value": {
                        "type": "string",
                        "description": "The SAP recommended or target value (empty string if no recommendation)"
                    },
                    "action_status": {
                        "type": "string",
                        "enum": ["Change Required", "Verify", "No Action", "Monitor"],
                        "description": "Action status: 'Change Required' if current differs from recommended, 'Verify' if values match but need verification, 'No Action' if informational only, 'Monitor' if OK but needs monitoring"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["High", "Medium", "Low"],
                        "description": "Priority: 'High' for critical/red status, 'Medium' for warnings/yellow, 'Low' for informational"
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what this parameter controls"
                    },
                    "source_section": {
                        "type": "string",
                        "description": "The section/chapter in the document where this parameter was found"
                    }
                },
                "required": ["parameter_name", "area", "current_value", "recommended_value", "action_status", "priority", "description", "source_section"],
                "additionalProperties": False
            }
        },
        "extraction_notes": {
            "type": "string",
            "description": "Any notes about the extraction process or data quality"
        }
    },
    "required": ["parameters", "extraction_notes"],
    "additionalProperties": False
}

EXTRACTION_PROMPT = """You are an expert SAP Basis consultant specializing in EarlyWatch Alert analysis. Your task is to perform an EXHAUSTIVE extraction of ALL parameter-related information from this SAP EarlyWatch Alert (EWA) report.

## EXTRACTION SCOPE - Extract parameters from ALL these sections:

### 1. SYSTEM CONFIGURATION PARAMETERS
- Instance profile parameters (DEFAULT.PFL, instance profiles)
- Start profile parameters
- Operation mode parameters
- Logon group configurations

### 2. SAP HANA PARAMETERS (if applicable)
- global.ini settings
- indexserver.ini parameters
- nameserver.ini parameters
- daemon.ini parameters
- Memory allocation parameters (global_allocation_limit, statement_memory_limit)
- Thread/parallelism parameters (parallel_merge_threads, max_concurrency)
- Table preload parameters
- Persistence parameters
- SQL optimizer parameters

### 3. DATABASE PARAMETERS (for any DB type)
- Oracle: SGA, PGA, shared_pool_size, db_cache_size, processes, sessions
- SQL Server: max server memory, max degree of parallelism
- DB2: buffer pools, sort heap, package cache
- MaxDB: cache sizes, data/log volumes
- ASE: memory pools, procedure cache

### 4. SAP KERNEL/WORK PROCESS PARAMETERS
- rdisp/* parameters (wp_no_dia, wp_no_btc, wp_no_spo, wp_no_enq, wp_no_vb, wp_no_vb2)
- em/* parameters (initial_size_MB, blocksize_KB, global_area_MB)
- abap/* parameters (heap_area_dia, heap_area_nondia, heap_area_total)
- rfc/* parameters (max_comm_entries, max_own_used_wp)
- icm/* parameters (server_port, max_conn, keep_alive_timeout)
- ms/* parameters (message server settings)

### 5. MEMORY MANAGEMENT PARAMETERS
- Extended Memory settings
- Roll area/buffer settings
- Paging area settings
- Buffer pool sizes (nametab, program, CUA, screen, calendar)
- Table buffer parameters (zcsa/table_buffer_area)

### 6. PERFORMANCE-RELATED PARAMETERS
- Enqueue parameters
- Update parameters
- Spool parameters
- Background processing parameters
- Lock management parameters

### 7. SECURITY PARAMETERS
- login/* parameters
- auth/* parameters
- ssl/* parameters
- snc/* parameters
- icf/* parameters

### 8. NETWORK/COMMUNICATION PARAMETERS
- sapgw/* parameters
- gw/* parameters (gateway settings)
- rfc/* parameters
- http/* parameters

### 9. JAVA STACK PARAMETERS (if applicable)
- JVM heap settings (-Xmx, -Xms, -XX parameters)
- Server node parameters
- ICM parameters for Java
- SDM parameters

### 10. OPERATING SYSTEM LEVEL RECOMMENDATIONS
- Kernel parameters (Linux: shmmax, shmall, sem, file-max)
- Swap space recommendations
- File system parameters
- Network kernel parameters

## ACTION STATUS CLASSIFICATION (CRITICAL):

For EACH parameter, you MUST determine the action_status and priority:

### action_status values:
1. **"Change Required"** - Use when:
   - Current value differs from recommended value
   - Report explicitly states a change is needed
   - Red status indicator with specific target value
   - SAP Note recommends a different value

2. **"Verify"** - Use when:
   - Recommended value matches current value (already compliant)
   - Report shows parameter was recently changed and needs verification
   - Yellow status indicating review needed

3. **"No Action"** - Use when:
   - Parameter is displayed for INFORMATION ONLY (no recommended value)
   - Current configuration stats (e.g., OS limits, file descriptors, memory stats)
   - Parameter appears in "OK" status tables with no recommendation
   - Historical/trend data without action items
   - Empty recommended_value field

4. **"Monitor"** - Use when:
   - Status is OK but flagged for ongoing monitoring
   - Parameter is within acceptable range but trending toward limits
   - Periodic review recommended

### priority values:
- **"High"** - Red status, critical alerts, security vulnerabilities, performance degradation
- **"Medium"** - Yellow/warning status, optimization opportunities, best practice deviations
- **"Low"** - Informational, green/OK status, no immediate action needed

## EXTRACTION RULES:

1. **Be INCLUSIVE**: Extract ANY mention of a parameter, even if:
   - Only the current value is shown (no recommendation) → mark as "No Action"
   - It appears in a status table showing "OK" → mark as "No Action" or "Monitor"
   - It's mentioned in narrative text
   - It's part of a comparison or trend analysis

2. **Parameter identification patterns - Look for**:
   - Explicit parameter tables with Current/Recommended columns
   - Alert sections with parameter references
   - Configuration check results
   - Trend analysis showing parameter changes over time
   - "Should be" or "must be" statements with parameter names
   - SAP Notes references that mention parameter changes
   - Red/Yellow/Green status indicators with parameters

3. **Section-by-section scanning** - Thoroughly check these EWA report sections:
   - Executive Summary
   - Service Summary / Recommendations Overview
   - Hardware Configuration Analysis
   - SAP HANA Database Analysis (memory, disk, CPU, alerts)
   - Database Performance Analysis
   - SAP Memory Configuration
   - Work Process Configuration
   - Buffer Analysis
   - Application Performance
   - Background Processing
   - Update Processing
   - Spool Analysis
   - Security Recommendations
   - SAP Notes Recommendations
   - Configuration Validation
   - Appendices and Detailed Tables

4. **Area classification**:
   - "SAP HANA" - All HANA-specific parameters
   - "Database" - Non-HANA database parameters (Oracle, SQL Server, DB2, etc.)
   - "SAP Kernel" - Kernel and dispatcher parameters
   - "Profile Parameters" - Instance/default profile settings
   - "Application" - Application-layer settings
   - "Memory/Buffer" - Memory management and buffer configurations
   - "Operating System" - OS-level kernel parameters
   - "Network" - Gateway, RFC, ICM network settings
   - "General" - Parameters that don't fit other categories

## CRITICAL REQUIREMENTS:
- Use empty string for current_value if not specified in the report
- Use empty string for recommended_value if no recommendation exists
- ALWAYS set action_status based on the classification rules above
- Parameters with empty recommended_value should be "No Action" with "Low" priority
- Scan EVERY section including appendices and detailed tables
- Include parameters even from "informational" or "OK status" sections
- Capture parameters from embedded SAP Note recommendations
- In extraction_notes, summarize sections analyzed and any data quality observations

Analyze the following EWA report completely and extract ALL parameters:

"""


class ParameterExtractionAgent:
    """Agent for extracting parameter recommendations using GPT-5-mini."""
    
    def __init__(self, client, model: str = None):
        """
        Initialize the parameter extraction agent.
        
        Args:
            client: Azure OpenAI client instance
            model: Model deployment name (defaults to AZURE_OPENAI_FAST_MODEL or gpt-4.1-mini)
        """
        self.client = client
        # Use gpt-5-mini specifically for parameter extraction
        self.model = model or os.getenv("AZURE_OPENAI_PARAM_MODEL", "gpt-5-mini")
        self.schema = PARAMETER_SCHEMA
        self.prompt = EXTRACTION_PROMPT
    
    async def extract(self, markdown_content: str) -> Dict[str, Any]:
        """
        Extract parameter recommendations from markdown content.
        
        Args:
            markdown_content: The EWA report markdown content
            
        Returns:
            Dictionary with 'parameters' list, 'extraction_notes', and 'summary'
        """
        if not markdown_content or not markdown_content.strip():
            return {"parameters": [], "extraction_notes": "Empty input content", "summary": self.get_summary_stats([])}
        
        try:
            result = await self._call_api(markdown_content)
            
            # Validate result structure
            if not isinstance(result, dict):
                return {"parameters": [], "extraction_notes": "Invalid response format", "summary": self.get_summary_stats([])}
            
            parameters = result.get("parameters", [])
            if not isinstance(parameters, list):
                parameters = []
            
            # Filter out invalid entries and apply post-processing
            valid_params = []
            for param in parameters:
                if isinstance(param, dict) and param.get("parameter_name"):
                    recommended_value = str(param.get("recommended_value", ""))
                    action_status = str(param.get("action_status", ""))
                    priority = str(param.get("priority", ""))
                    
                    # Auto-classify if action_status is missing or recommended_value is empty
                    if not recommended_value.strip():
                        action_status = ACTION_STATUS_NO_ACTION
                        priority = PRIORITY_LOW
                    elif not action_status:
                        # Default to Change Required if has recommendation but no status
                        action_status = ACTION_STATUS_CHANGE_REQUIRED
                        priority = priority or PRIORITY_MEDIUM
                    
                    # Ensure valid enum values
                    if action_status not in [ACTION_STATUS_CHANGE_REQUIRED, ACTION_STATUS_VERIFY, 
                                              ACTION_STATUS_NO_ACTION, ACTION_STATUS_MONITOR]:
                        action_status = ACTION_STATUS_NO_ACTION
                    
                    if priority not in [PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]:
                        priority = PRIORITY_LOW
                    
                    valid_params.append({
                        "parameter_name": str(param.get("parameter_name", "")),
                        "area": str(param.get("area", "General")),
                        "current_value": str(param.get("current_value", "")),
                        "recommended_value": recommended_value,
                        "action_status": action_status,
                        "priority": priority,
                        "description": str(param.get("description", "")),
                        "source_section": str(param.get("source_section", "")),
                    })
            
            summary = self.get_summary_stats(valid_params)
            print(f"[ParameterExtractionAgent] Extracted {len(valid_params)} valid parameters")
            print(f"[ParameterExtractionAgent] Summary: {summary}")
            
            return {
                "parameters": valid_params,
                "extraction_notes": result.get("extraction_notes", ""),
                "summary": summary
            }
            
        except Exception as e:
            print(f"[ParameterExtractionAgent] Error during extraction: {e}")
            return {"parameters": [], "extraction_notes": f"Extraction error: {str(e)}", "summary": self.get_summary_stats([])}
    
    @staticmethod
    def filter_by_action(parameters: List[Dict[str, Any]], statuses: List[str]) -> List[Dict[str, Any]]:
        """
        Filter parameters by action status.
        
        Args:
            parameters: List of parameter dictionaries
            statuses: List of action_status values to include (e.g., ["Change Required", "Verify"])
            
        Returns:
            Filtered list of parameters matching any of the specified statuses
        """
        if not statuses:
            return parameters
        return [p for p in parameters if p.get("action_status") in statuses]
    
    @staticmethod
    def filter_by_priority(parameters: List[Dict[str, Any]], priorities: List[str]) -> List[Dict[str, Any]]:
        """
        Filter parameters by priority.
        
        Args:
            parameters: List of parameter dictionaries
            priorities: List of priority values to include (e.g., ["High", "Medium"])
            
        Returns:
            Filtered list of parameters matching any of the specified priorities
        """
        if not priorities:
            return parameters
        return [p for p in parameters if p.get("priority") in priorities]
    
    @staticmethod
    def get_summary_stats(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get summary statistics for parameters by action status and priority.
        
        Args:
            parameters: List of parameter dictionaries
            
        Returns:
            Dictionary with counts by action_status and priority
        """
        by_action = {
            ACTION_STATUS_CHANGE_REQUIRED: 0,
            ACTION_STATUS_VERIFY: 0,
            ACTION_STATUS_NO_ACTION: 0,
            ACTION_STATUS_MONITOR: 0,
        }
        by_priority = {
            PRIORITY_HIGH: 0,
            PRIORITY_MEDIUM: 0,
            PRIORITY_LOW: 0,
        }
        
        for param in parameters:
            action = param.get("action_status", ACTION_STATUS_NO_ACTION)
            priority = param.get("priority", PRIORITY_LOW)
            
            if action in by_action:
                by_action[action] += 1
            if priority in by_priority:
                by_priority[priority] += 1
        
        return {
            "total": len(parameters),
            "by_action_status": by_action,
            "by_priority": by_priority,
            "actionable": by_action[ACTION_STATUS_CHANGE_REQUIRED] + by_action[ACTION_STATUS_VERIFY],
        }
    
    async def _call_api(self, markdown_content: str) -> Dict[str, Any]:
        """Call the OpenAI API with structured output."""
        
        # No strict character limit, allow full content to be sent
        # max_chars = 100000
        # if len(markdown_content) > max_chars:
        #    markdown_content = markdown_content[:max_chars] + "\n\n[Content truncated...]"
        
        user_message = f"{self.prompt}\n\n{markdown_content}"
        
        # Prepare strict schema for structured outputs
        strict_schema = self._make_strict_schema(self.schema)
        
        text_format = {
            "format": {
                "type": "json_schema",
                "name": "extract_parameters",
                "schema": strict_schema,
                "strict": True,
            }
        }
        
        # Call API using responses endpoint with medium reasoning effort
        response = await asyncio.to_thread(
            lambda: self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": [{"type": "input_text", "text": user_message}]}],
                text=text_format,
                reasoning={"effort": "medium"},
                max_output_tokens=16384,
            )
        )
        
        # Log token usage
        try:
            usage = getattr(response, "usage", None)
            if usage:
                in_tok = getattr(usage, "input_tokens", None)
                out_tok = getattr(usage, "output_tokens", None)
                print(f"[ParameterExtractionAgent] Token usage: input={in_tok}, output={out_tok}")
        except Exception:
            pass
        
        # Extract structured output
        try:
            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                    return parsed[0]
        except Exception:
            pass
        
        # Fallback to output_text
        text = getattr(response, "output_text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        
        return {"parameters": []}
    
    def _make_strict_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure schema has additionalProperties: false on all objects."""
        import copy
        
        def visit(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    node["additionalProperties"] = False
                    if "properties" in node:
                        for k, v in node["properties"].items():
                            node["properties"][k] = visit(v)
                if "items" in node:
                    node["items"] = visit(node["items"])
            return node
        
        return visit(copy.deepcopy(schema))
