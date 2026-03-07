# Fan-Out Sub-Agent Architecture with ewa-mcp Preprocessor

Redesign the EWA analysis workflow to use ewa-mcp's chunking and Priority Table alert extraction as an in-process preprocessor, then fan out parallel gpt-5-mini sub-agents per alert, producing the same `_AI.json` output with lower cost, faster execution, and partial-result resilience.

> **Note**: ewa-mcp is not yet deployed. All reusable code (chunker, models, alert extractor) will be ported directly into the ewa_analyzer backend as local modules — no external service dependency.

## Decisions (Confirmed)

| Decision | Choice |
|----------|--------|
| Alert source | **Priority Table extractor** (ewa-mcp's `VisionAlertExtractor`, pages 1–4). Replaces Check Overview extractor. |
| Chunk identifier | **`link_alerts_to_chunks()` first** (page/category overlap, zero cost), then gpt-5-mini LLM only for unmatched alerts. |
| Failure strategy | **Return partial results**. Failed sub-agents produce placeholder entries ("Unknown") rather than blocking the whole analysis. |

## Current vs. Proposed Architecture

### Current (Monolithic)
```
PDF → pymupdf4llm → Markdown (~94K tokens)
    → Vision (Check Overview, pages 1-5)
    → Single large-model call (full markdown + Check Overview) → Complete JSON
```

### Proposed (Fan-Out)
```
PDF
 ├─ pymupdf4llm → Markdown
 ├─ MarkdownChunker → Chunk[] (section_path, category, page_range)
 ├─ VisionAlertExtractor (pages 1-4) → Alert[] (title, severity, category, sap_notes)
 └─ link_alerts_to_chunks() → Alert[].evidence_chunk_ids
     │  ↓ (unmatched alerts only)
     │  gpt-5-mini Chunk Identifier (~1K tokens)
     │
     ▼
 Parallel Sub-Agents (gpt-5-mini, asyncio.gather):
 ├─ Alert Agent ×N  →  Key Finding + Recommendation (per alert)
 ├─ Positive Findings Agent  →  Positive Findings[]
 └─ Capacity Agent  →  Capacity Outlook {}
     │
     ▼
 Stitcher (deterministic + one small LLM call):
 ├─ System Metadata ← pdf_metadata_extractor (no LLM)
 ├─ Chapters Reviewed ← section headers (no LLM)
 ├─ Overall Risk ← severity logic (no LLM)
 ├─ System Health Overview ← rubric on alerts (no LLM)
 ├─ Executive Summary ← gpt-5-mini on merged findings (~5K tokens)
 └─ Assemble → schema validation → _AI.json + _AI.md
```

## Implementation Steps

### Phase 1: Port ewa-mcp Preprocessor (In-Process)

All code ported from `C:\GenAI\ewa-mcp` into `C:\GenAI\ewa_analyzer\backend`. No Azure Functions, Search, or Event Grid needed.

1. **Port Pydantic models** → `backend/models/`:
   - `alert.py`: `Alert`, `AlertExtractionResult`, `Severity`, `Category` enums from `ewa-mcp/shared/models/alert.py`
   - `chunk.py`: `Chunk` model from `ewa-mcp/shared/models/chunk.py`
   - Strip `content_vector` field (not needed), keep all other fields

2. **Port `MarkdownChunker`** → `backend/utils/markdown_chunker.py`:
   - From `ewa-mcp/processor/chunkers/markdown_chunker.py`
   - Keep: `_split_by_headers()`, `_build_section_path()`, `_extract_severity()`, `_extract_category()`, `_extract_sap_notes()`, `_split_large_chunk()`, `link_alerts_to_chunks()`
   - Max chunk size: 4000 chars
   - Returns `List[Chunk]` in memory (no indexing)

3. **Port `VisionAlertExtractor`** → `backend/agent/vision_alert_extractor.py`:
   - From `ewa-mcp/processor/extractors/alert_extractor.py`
   - Adapt to use Azure OpenAI Responses API (current backend standard) instead of Chat Completions
   - Renders pages 1–4 as images, sends to vision model
   - Returns `AlertExtractionResult` with `Alert[]`
   - **Replaces** existing `check_overview_vision_extractor.py` in the fan-out path

4. **Port PDF extraction helper** — Reuse existing `pymupdf4llm.to_markdown()` from `pdf_markdown_converter.py`. Add page image rendering for pages 1–4 (already exists in `check_overview_vision_extractor.py`'s `render_pages_to_images()`).

### Phase 2: Chunk Identifier (Hybrid)

5. **Enhance `link_alerts_to_chunks()`** with LLM fallback:
   - First pass: page/category overlap matching (from ewa-mcp, zero cost)
   - Second pass: For alerts with 0 matched chunks, call gpt-5-mini with `{alert.title} + [chunk.section_path list]` → returns matching section_paths
   - Store matched chunk IDs on each `Alert.evidence_chunk_ids`

### Phase 3: Sub-Agent Framework

6. **Create sub-schema files** in `backend/schemas/`:
   - `alert_finding_schema.json`: Schema for one Key Finding + one Recommendation
   - `positive_findings_schema.json`: Schema for Positive Findings array
   - `capacity_outlook_schema.json`: Schema for Capacity Outlook object

7. **Create sub-agent prompt files** in `backend/prompts/`:
   - `alert_sub_agent_prompt.md`: Focused prompt for analyzing one alert with its evidence chunks
   - `positive_findings_prompt.md`: Prompt for extracting positive findings from green-rated content
   - `capacity_sub_agent_prompt.md`: Prompt for capacity analysis from capacity-related chunks
   - `executive_summary_prompt.md`: Prompt for synthesizing Executive Summary from assembled findings

8. **Create `backend/agent/alert_sub_agent.py`**:
   - Input: one `Alert` + list of `Chunk` contents (evidence markdown, ~3–8K tokens)
   - Output: `{Key Finding, Recommendation}` JSON matching schema subset
   - Uses gpt-5-mini via Responses API with Structured Outputs
   - On failure: returns placeholder `{Finding: alert.title, Impact: "Unknown", ...}`

9. **Create `backend/agent/capacity_sub_agent.py`**:
   - Input: chunks where `category in [database, data_volume, performance]`
   - Output: `{Database Growth, CPU Utilization, Memory Utilization, Summary}`

10. **Create `backend/agent/positive_findings_sub_agent.py`**:
    - Input: chunks with `severity == info` or low severity + alert descriptions
    - Output: `[{Area, Description}]` array

11. **Create `backend/agent/executive_summary_agent.py`**:
    - Input: assembled Key Findings + Recommendations + Capacity Outlook (~5K tokens)
    - Output: Executive Summary string (bullet-point format)
    - No document content needed — works purely from sub-agent outputs

### Phase 4: Fan-Out Orchestrator

12. **Create `backend/agent/fan_out_orchestrator.py`**:

    ```python
    async def run_fan_out_analysis(markdown, pdf_bytes, blob_name) -> dict:
        # 1. Chunk markdown
        chunks = MarkdownChunker(max_chunk_size=4000).chunk_document(markdown, ...)

        # 2. Extract alerts via Priority Table vision
        images = render_pages_to_images(pdf_bytes, [0,1,2,3])
        alert_result = VisionAlertExtractor(...).extract_alerts(images, ...)
        alerts = alert_result.alerts

        # 3. Link alerts → chunks (page/category overlap + LLM fallback)
        alerts = link_alerts_to_chunks(alerts, chunks)
        alerts = await llm_fallback_linking(alerts, chunks)  # unmatched only

        # 4. Fan out sub-agents (parallel)
        tasks = []
        for alert in alerts:
            evidence = [c for c in chunks if c.chunk_id in alert.evidence_chunk_ids]
            tasks.append(alert_sub_agent.run(alert, evidence))
        tasks.append(capacity_sub_agent.run(capacity_chunks))
        tasks.append(positive_findings_sub_agent.run(positive_chunks))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 5. Stitch (deterministic + Executive Summary LLM call)
        summary_json = stitch_results(results, alerts, chunks, blob_name)
        return summary_json
    ```

13. **Stitcher logic** inside `fan_out_orchestrator.py`:
    - **System Metadata**: From `pdf_metadata_extractor` + blob metadata (no LLM)
    - **Chapters Reviewed**: From chunker section headers (no LLM)
    - **Overall Risk**: `any(sev == very_high or sev == high) → "high"`, `any(medium) → "medium"`, else `"low"` (no LLM)
    - **System Health Overview**: Deterministic rubric on alert categories/severities (no LLM)
    - **Key Findings + Recommendations**: Merge sub-agent outputs, assign sequential IDs (KF-01→REC-01, KF-02→REC-02, ...)
    - **Positive Findings**: From positive findings sub-agent
    - **Capacity Outlook**: From capacity sub-agent
    - **Executive Summary**: Single gpt-5-mini call (~5K tokens input)
    - **Schema validation**: Existing `ewa_summary_schema.json` + `JSONRepair`

14. **Partial result handling**: Each `asyncio.gather` result is checked:
    - If a sub-agent returned an exception → log warning, insert placeholder entry
    - Placeholder Key Finding: `{Issue ID: "KF-XX", Area: alert.title, Finding: alert.description or "Analysis failed", Impact: "Unknown", Business impact: "Unknown", Severity: alert.severity mapped, Source: "Priority Table"}`
    - Placeholder Recommendation: `{Action: "Manual review required", Preventative Action: "Unknown", Estimated Effort: {analysis: "medium", implementation: "medium"}}`

### Phase 5: Wire Into Workflow

15. **Update `backend/core/runtime_config.py`**:
    ```python
    ANALYSIS_MODE = os.getenv("ANALYSIS_MODE", "monolithic")  # "monolithic" | "fan_out"
    FAN_OUT_MODEL = os.getenv("FAN_OUT_MODEL", "gpt-5-mini")
    MAX_PARALLEL_SUB_AGENTS = int(os.getenv("MAX_PARALLEL_SUB_AGENTS", "5"))
    ```

16. **Update `workflow_orchestrator.py` `run_analysis_step()`**:
    - Branch on `ANALYSIS_MODE`:
      - `"monolithic"` → existing `OpenAIEWAAgent` / `AnthropicEWAAgent` path (unchanged)
      - `"fan_out"` → calls `fan_out_orchestrator.run_fan_out_analysis()`
    - Both paths produce the same `state.summary_json` dict
    - All downstream (save_results_step, frontend, exports) unchanged

17. **Remove `extract_check_overview_step()`** from the fan-out path — replaced by `VisionAlertExtractor` running inside the orchestrator. Keep it for monolithic mode.

## Token Budget (Fan-Out, All gpt-5-mini)

| Step | Tokens |
|------|--------|
| Priority Table Vision (pages 1-4) | ~5K |
| link_alerts_to_chunks (deterministic) | 0 |
| LLM fallback for unmatched (~2-3 alerts) | ~1K |
| 15 Alert Sub-Agents × ~5K each | ~75K |
| Positive Findings Agent | ~5K |
| Capacity Agent | ~5K |
| Executive Summary Agent | ~5K |
| **Total** | **~96K** |
| **Current monolithic (gpt-5/5.2)** | **~94K** |

Same volume, entirely on gpt-5-mini. Parallel execution cuts wall-clock time. Partial failures don't block results.

## Files Created/Modified Summary

### New Files
| File | Purpose |
|------|---------|
| `backend/models/alert.py` | Alert, Severity, Category models (from ewa-mcp) |
| `backend/models/chunk.py` | Chunk model (from ewa-mcp) |
| `backend/models/__init__.py` | Package init |
| `backend/utils/markdown_chunker.py` | MarkdownChunker + link_alerts_to_chunks (from ewa-mcp) |
| `backend/agent/vision_alert_extractor.py` | Priority Table vision extractor (from ewa-mcp, adapted to Responses API) |
| `backend/agent/alert_sub_agent.py` | Per-alert sub-agent |
| `backend/agent/capacity_sub_agent.py` | Capacity analysis sub-agent |
| `backend/agent/positive_findings_sub_agent.py` | Positive findings sub-agent |
| `backend/agent/executive_summary_agent.py` | Executive Summary synthesizer |
| `backend/agent/fan_out_orchestrator.py` | Fan-out orchestrator + stitcher |
| `backend/schemas/alert_finding_schema.json` | Sub-schema for one KF+REC pair |
| `backend/schemas/positive_findings_schema.json` | Sub-schema for Positive Findings |
| `backend/schemas/capacity_outlook_schema.json` | Sub-schema for Capacity Outlook |
| `backend/prompts/alert_sub_agent_prompt.md` | Alert analysis prompt |
| `backend/prompts/positive_findings_prompt.md` | Positive findings prompt |
| `backend/prompts/capacity_sub_agent_prompt.md` | Capacity analysis prompt |
| `backend/prompts/executive_summary_prompt.md` | Executive summary synthesis prompt |

### Modified Files
| File | Change |
|------|--------|
| `backend/core/runtime_config.py` | Add `ANALYSIS_MODE`, `FAN_OUT_MODEL`, `MAX_PARALLEL_SUB_AGENTS` |
| `backend/workflow_orchestrator.py` | Branch `run_analysis_step()` on `ANALYSIS_MODE` |

### Unchanged
- Frontend (SAPUI5), exports, chat router, save_results_step — all consume `summary_json` as before
- Monolithic path preserved as default fallback
