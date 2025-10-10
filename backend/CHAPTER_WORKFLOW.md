# Chapter-by-Chapter Analysis Workflow

## Overview

The EWA Analyzer now supports a **chapter-by-chapter analysis workflow** that ensures comprehensive coverage of all document sections. This addresses the requirement to systematically review every chapter so that no findings are missed.

## Workflow Steps

### Step 0: PDF to Markdown Conversion
**Critical for large documents**: To avoid Azure OpenAI's 50-image limit, the PDF is first converted to markdown:
- Uses existing markdown conversion pipeline
- Markdown is text-only, bypassing image quota
- Preserves document structure (headings, paragraphs, tables)
- Essential for EWA reports which typically exceed 50 pages

### Step 1: Chapter Enumeration
The agent examines the **markdown** document and identifies all chapters/sections present:
- Extracts chapter titles
- Records page ranges
- Identifies subsections
- Creates a complete table of contents
- **Uses markdown input** to avoid 50-image limit

**Schema**: `backend/schemas/chapter_enumeration_schema.json`  
**Prompt**: `backend/prompts/chapter_enumeration_prompt.md`  
**Input**: Markdown text (not PDF)

### Step 2: Chapter-by-Chapter Analysis
For each identified chapter, the agent performs a detailed analysis:
- Extracts all key findings from that specific chapter
- Identifies recommendations related to those findings
- Captures positive observations
- Notes metrics and profile parameters

The analysis is scoped to the chapter's content only, avoiding duplication across chapters.

**Schema**: `backend/schemas/chapter_analysis_schema.json`  
**Prompt**: `backend/prompts/chapter_analysis_prompt.md`

### Step 3: Merge and Consolidation
All chapter-level analyses are merged into a final comprehensive summary:
- **Key Findings** are renumbered globally (KF-01, KF-02, etc.)
- **Recommendations** are renumbered and linked to global finding IDs (REC-01 → KF-01)
- **Positive findings** are deduplicated
- **System Health Overview** is derived from all findings
- **Executive Summary** is generated from aggregate data
- **Overall Risk** is calculated from severity distribution

**Merge Logic**: `backend/utils/chapter_merge.py`

### Step 4: KPI Extraction
After the chapter-based analysis is complete, KPIs are extracted via the image-based agent (unchanged from existing workflow).

## Architecture

```
EWAAgent
├── enumerate_chapters(markdown) → chapter_enumeration_result
│   └── Uses markdown input to avoid 50-image limit
├── analyze_chapter(chapter_info, pdf_data) → chapter_analysis
│   ├── Uses chapter-specific schema
│   └── Scoped to chapter pages (PDF input OK for small chunks)
└── run(markdown, pdf_data) → full_summary (legacy single-pass)

EWAWorkflowOrchestrator
├── run_chapter_by_chapter_analysis_step(state)
│   ├── Downloads/converts PDF to markdown
│   ├── Calls enumerate_chapters(markdown) ← avoids image limit
│   ├── Loops through chapters calling analyze_chapter(pdf_data)
│   ├── Calls merge_chapter_analyses()
│   └── Extracts KPIs
└── run_analysis_step(state) (legacy single-pass)

chapter_merge.py
└── merge_chapter_analyses(chapter_analyses, metadata, chapters_reviewed)
    ├── _merge_key_findings() → renumbers findings globally
    ├── _merge_recommendations() → maps to global finding IDs
    ├── _derive_health_overview() → aggregates health ratings
    ├── _generate_executive_summary() → creates bullet summary
    └── _derive_overall_risk() → calculates risk level
```

## Usage

### Backend API

The chapter-by-chapter workflow is **enabled by default**. To use it:

```python
# Default behavior (chapter-by-chapter)
result = await ewa_orchestrator.execute_workflow(
    blob_name="EWA_Report.pdf",
    skip_markdown=True,
    chapter_by_chapter=True  # This is the default
)
```

To revert to the legacy single-pass workflow:

```python
result = await ewa_orchestrator.execute_workflow(
    blob_name="EWA_Report.pdf",
    skip_markdown=True,
    chapter_by_chapter=False  # Explicitly disable
)
```

### REST API

**POST /api/process-and-analyze**

Request body:
```json
{
  "blob_name": "EWA_Report.pdf",
  "chapter_by_chapter": true
}
```

The `chapter_by_chapter` parameter defaults to `true`, so you can omit it:
```json
{
  "blob_name": "EWA_Report.pdf"
}
```

## Benefits

1. **Comprehensive Coverage**: Every chapter is explicitly enumerated and reviewed
2. **No Missed Findings**: The agent cannot skip chapters or sections
3. **Source Attribution**: Each finding is linked to its source chapter
4. **Scalability**: Large documents are processed in manageable chunks
5. **Transparency**: The "Chapters Reviewed" field in the output shows exactly what was analyzed

## Output Schema

The final merged output conforms to the existing `ewa_summary_schema.json` with one addition:

```json
{
  "Schema Version": "1.1",
  "Chapters Reviewed": [
    "Executive Summary",
    "System Configuration",
    "Performance Analysis",
    ...
  ],
  "System Metadata": {...},
  "Key Findings": [...],
  "Recommendations": [...],
  ...
}
```

The `"Chapters Reviewed"` array provides an audit trail of all chapters that were analyzed.

## Performance Considerations

- **Token Usage**: Chapter-by-chapter mode makes multiple LLM calls (1 for enumeration + N for chapters)
- **Time**: Total processing time is longer than single-pass mode
- **Accuracy**: Improved coverage often justifies the additional cost
- **Image Limit**: Markdown-based enumeration avoids Azure's 50-image limit for large PDFs
- **Parallelization**: Future enhancement could analyze chapters in parallel

## Migration Notes

- Existing code will automatically use the new workflow (default behavior)
- To maintain legacy behavior, explicitly set `chapter_by_chapter=False`
- The output schema remains backward-compatible (only adds "Chapters Reviewed")
- All existing integrations continue to work without changes

## Testing

To test the chapter-by-chapter workflow:

1. Upload an EWA PDF to Azure Blob Storage
2. Call `/api/process-and-analyze` with the blob name
3. Verify the response includes "Chapters Reviewed" array
4. Check logs for "[CHAPTER MODE]" messages indicating the workflow was used

Example log output:
```
[WORKFLOW] Mode: Chapter-by-Chapter
[CHAPTER MODE] Step 1: Enumerating chapters...
[CHAPTER MODE] Found 12 chapters across 85 pages
[CHAPTER MODE] Step 2: Analyzing 12 chapters individually...
[CHAPTER MODE] Analyzing 1/12: CH-01 - Executive Summary
[CHAPTER MODE] CH-01 complete: 2 findings, 2 recommendations
...
[CHAPTER MODE] Step 3: Merging chapter analyses...
[CHAPTER MODE] Merge complete: 24 total findings
[CHAPTER MODE] Step 4: Extracting KPIs via image agent...
```

## Troubleshooting

**Issue**: "Too many images in request. Max is 50."  
**Solution**: ✅ Fixed! Chapter enumeration now uses markdown instead of PDF to bypass the image limit

**Issue**: Chapter enumeration returns no chapters  
**Solution**: Check if the markdown conversion preserved section headers; verify markdown quality

**Issue**: "Markdown conversion required but not available"  
**Solution**: Ensure the PDF has been converted to markdown first, or check blob storage for the .md file

**Issue**: Some chapters fail to analyze  
**Solution**: The workflow continues even if individual chapters fail; check logs for specific errors

**Issue**: Findings are duplicated across chapters  
**Solution**: Ensure the chapter analysis prompt emphasizes scoping to chapter content only

**Issue**: High token usage  
**Solution**: Consider falling back to single-pass mode for very large documents with many chapters
