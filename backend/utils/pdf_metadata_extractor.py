"""Utility functions for extracting metadata from PDF files using AI."""

import os
import re
import io
from datetime import datetime
from typing import Dict, Any
import asyncio
import json

from openai import AsyncAzureOpenAI
import fitz  # PyMuPDF

from fastapi import HTTPException


# AI extraction prompt
def _get_extraction_prompt() -> str:
    return """You are an extraction bot. Extract the System ID and Report End Date from the provided text.

Instructions:
1. Find the System ID - it's typically labeled as "System ID" followed by a short alphanumeric code
2. Find the Report End Date - Look for phrases like "Reporting Period", "Analysis Period", or "Period" and extract the end date. If multiple dates are present, choose the later date which represents when the report coverage ends.
3. Return ONLY valid JSON with these exact keys: system_id, report_date
4. Format the report_date as dd.mm.yyyy regardless of input format
5. If you cannot find either value, return that key with an empty string

Example output:
{"system_id": "ERP", "report_date": "09.06.2025"}

Text to analyze:
"""


def extract_text_from_first_page(pdf_bytes: bytes) -> str:
    """Extract text from the first page of a PDF file."""
    try:
        # Create a BytesIO object from the PDF bytes
        pdf_stream = io.BytesIO(pdf_bytes)
        
        # Open the PDF with PyMuPDF
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        
        # Extract text from the first page
        first_page = doc[0]
        text = first_page.get_text()
        
        # Close the document
        doc.close()
        
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")


def _normalize_date_format(date_str: str) -> str:
    """Normalize various date formats to dd.mm.yyyy"""
    if not date_str:
        return ""
    
    # Replace various separators with dots
    normalized = date_str.replace('/', '.').replace('-', '.')
    
    try:
        # Parse the date
        if len(normalized) == 10 and normalized[2] == '.' and normalized[5] == '.':
            # Already in dd.mm.yyyy format
            datetime.strptime(normalized, "%d.%m.%Y")
            return normalized
        elif len(normalized) == 10 and normalized[4] == '.' and normalized[7] == '.':
            # In yyyy.mm.dd format
            dt = datetime.strptime(normalized, "%Y.%m.%d")
            return dt.strftime("%d.%m.%Y")
        elif len(normalized) == 8 and '.' not in normalized:
            # In ddmmyyyy format
            dt = datetime.strptime(normalized, "%d%m%Y")
            return dt.strftime("%d.%m.%Y")
        else:
            # Try to parse as dd.mm.yyyy
            datetime.strptime(normalized, "%d.%m.%Y")
            return normalized
    except ValueError:
        # If we can't parse it, return as is
        return date_str


def _parse_regex_fallback(text: str) -> Dict[str, str]:
    """Fallback regex-based extraction if AI fails."""
    # Extract System ID
    sid_patterns = [
        r'System\s*ID\s*[:\-]?\s*([A-Z0-9]{3,10})',
        r'SID\s*[:\-]?\s*([A-Z0-9]{3,10})',
        r'([A-Z0-9]{3,10})\s+System'
    ]
    
    system_id = ""
    for pattern in sid_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            system_id = match.group(1).upper()
            break
    
    # Extract Report Date
    date_patterns = [
        r'(\d{2}[./-]\d{2}[./-]\d{4})',  # dd.mm.yyyy or dd/mm/yyyy or dd-mm-yyyy
        r'(\d{2}[./-]\d{2}[./-]\d{2})',   # dd.mm.yy or dd/mm/yy or dd-mm-yy
        r'(\d{4}[./-]\d{2}[./-]\d{2})'    # yyyy.mm.dd or yyyy/mm/dd or yyyy-mm-dd
    ]
    
    report_date = ""
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            report_date = match.group(1)
            break
    
    # Normalize date format
    if report_date:
        report_date = _normalize_date_format(report_date)
    
    return {
        "system_id": system_id,
        "report_date": report_date
    }


async def extract_metadata_with_ai(pdf_bytes: bytes) -> Dict[str, Any]:
    """Extract system ID and report date from PDF using AI with fallback to regex."""
    # First try to extract text from the first page
    try:
        text = extract_text_from_first_page(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Could not extract text from PDF: {str(e)}")
    
    if not text:
        # If no text, fall back to regex on filename
        raise ValueError("No text found in first page of PDF")
    
    # Try AI extraction first
    try:
        # Import Azure OpenAI configuration from workflow orchestrator
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from workflow_orchestrator import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_FAST_MODEL
        
        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            raise ValueError("Azure OpenAI configuration not found")
        
        # Create Azure OpenAI client
        client = AsyncAzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )
        
        # Call the AI model
        response = await client.chat.completions.create(
            model=AZURE_OPENAI_FAST_MODEL,
            messages=[
                {"role": "system", "content": _get_extraction_prompt()},
                {"role": "user", "content": text[:4000]}  # Limit text to 4000 chars
            ],
            max_tokens=100,
            temperature=0
        )
        
        # Parse the response
        result_text = response.choices[0].message.content.strip()
        
        # Try to parse as JSON
        try:
            result = json.loads(result_text)
            
            # Validate required keys
            if "system_id" not in result or "report_date" not in result:
                raise ValueError("Missing required keys in AI response")
            
            # Normalize the date
            if result.get("report_date"):
                result["report_date"] = _normalize_date_format(result["report_date"])
            
            # Validate that we got meaningful values
            if result.get("system_id") and result.get("report_date"):
                return {
                    "system_id": result["system_id"],
                    "report_date": result["report_date"],
                    "report_date_str": result["report_date"]
                }
        except json.JSONDecodeError:
            # If JSON parsing fails, continue to fallback
            pass
            
    except Exception as e:
        # If AI fails, continue to fallback
        print(f"AI extraction failed: {str(e)}")
        pass
    
    # Fallback to regex extraction
    try:
        regex_result = _parse_regex_fallback(text)
        if regex_result.get("system_id") and regex_result.get("report_date"):
            # Parse the date for proper datetime object
            try:
                dt = datetime.strptime(regex_result["report_date"], "%d.%m.%Y")
                return {
                    "system_id": regex_result["system_id"],
                    "report_date": dt,
                    "report_date_str": regex_result["report_date"]
                }
            except ValueError:
                pass
    except Exception as e:
        print(f"Regex fallback failed: {str(e)}")
        pass
    
    # If both methods fail, raise an error
    raise HTTPException(
        status_code=400, 
        detail="Could not extract System ID and Report Date from PDF. Please use filename format <SID>_ddmmyy.pdf as fallback."
    )
