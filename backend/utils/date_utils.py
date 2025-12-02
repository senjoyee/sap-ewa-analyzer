"""
Shared date parsing utilities for the EWA Analyzer backend.

This module consolidates date parsing logic that was previously duplicated
across markdown_utils.py and html_utils.py.
"""

from datetime import datetime
from typing import Optional


def parse_date_any(date_str: str) -> Optional[datetime]:
    """
    Parse a date string in various formats and return a datetime object.
    
    Supported formats:
    - ISO format: YYYY-MM-DD
    - European format: DD.MM.YYYY
    - Slash format: DD/MM/YYYY
    - US format: MM/DD/YYYY (fallback)
    
    Args:
        date_str: The date string to parse
        
    Returns:
        datetime object if parsing succeeds, None otherwise
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    
    formats = [
        "%Y-%m-%d",      # ISO format
        "%d.%m.%Y",      # European format
        "%d/%m/%Y",      # Slash format
        "%m/%d/%Y",      # US format (fallback)
        "%Y/%m/%d",      # Alternative ISO
        "%d-%m-%Y",      # European with dashes
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def format_date_display(date_str: str, output_format: str = "%d %B %Y") -> str:
    """
    Parse a date string and format it for display.
    
    Args:
        date_str: The date string to parse
        output_format: The desired output format (default: "01 January 2025")
        
    Returns:
        Formatted date string, or original string if parsing fails
    """
    dt = parse_date_any(date_str)
    if dt:
        return dt.strftime(output_format)
    return date_str


def format_date_iso(date_str: str) -> str:
    """
    Parse a date string and format it as ISO (YYYY-MM-DD).
    
    Args:
        date_str: The date string to parse
        
    Returns:
        ISO formatted date string, or original string if parsing fails
    """
    dt = parse_date_any(date_str)
    if dt:
        return dt.strftime("%Y-%m-%d")
    return date_str
