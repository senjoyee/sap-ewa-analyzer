# Chapter Enumeration Task

You are analyzing an SAP EarlyWatch Alert (EWA) report. Your task is to systematically enumerate ALL chapters, sections, and major subsections present in the document.

## Instructions:

1. **Scan the entire document** from beginning to end
2. **Identify all major chapters/sections** - typically these include:
   - Table of Contents
   - Executive Summary
   - System Overview/Configuration
   - Performance Analysis
   - Database Analysis
   - Security Analysis
   - Capacity Planning
   - Technical Findings
   - Recommendations
   - Appendices
   - Any other major sections

3. **Record the following for each chapter:**
   - A unique chapter ID (CH-01, CH-02, etc.)
   - The exact title as it appears in the document
   - The starting page number
   - The ending page number (use start_page value if end is not determinable)
   - Key subsections within the chapter (use empty array [] if none)

4. **Be comprehensive** - do not skip any section, even if it appears minor
5. **Maintain order** - list chapters in the order they appear in the document
6. **Count total pages** in the document

## Output Format:

Return a JSON object that strictly conforms to the chapter enumeration schema. Include:
- An array of all chapters with their metadata
- Total page count
- Document type identification

Do not add any narrative or explanations outside the JSON structure. Focus solely on accurate, complete enumeration of the document structure.
