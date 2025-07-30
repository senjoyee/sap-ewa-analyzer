# EWA Analyzer KPI Trend Tracking Implementation Summary

## Overview
This document summarizes the implementation of KPI trend tracking functionality in the EWA Analyzer. The feature enables tracking performance trends over time by comparing current KPI values with previous values, and maintains consistency in KPI naming across analysis runs.

## Key Features Implemented

### 1. Schema Updates
- Modified `ewa_summary_schema.json` to include a `trend` object for each KPI with `direction` (up/down/flat) and optional `percent_change` fields
- Updated schema documentation to clarify canonical KPI usage

### 2. Prompt Engineering
- Enhanced `ewa_summary_prompt.md` to instruct the AI model to:
  - Use only canonical KPI names for consistency
  - Populate trend information by comparing with previous values
  - Add any new KPIs to a separate `additional_kpis` section

### 3. KPI Utility Functions
Created `kpi_utils.py` with functions for:
- Extracting customer/system identifiers from blob names
- Retrieving and saving canonical KPI lists from/to Azure Blob Storage
- Retrieving previous KPI data for trend calculation
- Calculating trend direction and percent change between current and previous KPI values

### 4. Workflow Orchestration
Updated `workflow_orchestrator.py` to:
- Extract customer/system information from blob names
- Retrieve previous KPI data and canonical KPI names
- Pass this information to the EWA agent
- Implement quality control for KPI name consistency
- Add rule-based approval logic for updating canonical KPI lists with new KPIs
- Persist canonical KPI lists per (customer, system) on first run

### 5. Agent Enhancements
Modified `ewa_agent.py` to:
- Accept previous KPI data and canonical KPI names as additional input
- Append this information to the prompt for the AI model
- Update internal methods to handle enhanced prompts

### 6. Trend Calculation Logic
Implemented and tested trend calculation that:
- Compares current KPI values with previous values
- Calculates percent change where possible
- Determines trend direction (up/down/flat)
- Handles various numeric formats and units

## Implementation Details

### Canonical KPI Management
- Each (customer, system) pair maintains its own canonical KPI list
- Canonical lists are persisted in Azure Blob Storage
- First run establishes the initial canonical list
- New KPIs are added to a separate `additional_kpis` section
- Rule-based approval automatically adds new KPIs to canonical lists

### Trend Calculation
- Extracts numeric values from KPI strings (handling units like %, GB, ms, etc.)
- Calculates percent change between current and previous values
- Determines trend direction based on percent change
- Handles cases where previous data is not available

### Quality Control
- Enforces use of canonical KPI names
- Merges additional KPIs into main KPI list
- Validates KPI name consistency across runs

## Testing
- Created and executed test script (`test_kpi_trends.py`) to verify trend calculation functionality
- Verified correct handling of various numeric formats and units
- Confirmed proper trend direction detection and percent change calculation

## Files Modified
1. `backend/schemas/ewa_summary_schema.json` - Schema updates
2. `backend/prompts/ewa_summary_prompt.md` - Prompt enhancements
3. `backend/utils/kpi_utils.py` - New utility functions
4. `backend/workflow_orchestrator.py` - Workflow logic
5. `backend/agent/ewa_agent.py` - Agent enhancements
6. `test_kpi_trends.py` - Test script

## Future Enhancements
- Implement manual approval process for canonical KPI updates
- Enhance numeric extraction for complex units and formats
- Add more sophisticated trend analysis algorithms
- Implement UI for reviewing and managing canonical KPI lists
