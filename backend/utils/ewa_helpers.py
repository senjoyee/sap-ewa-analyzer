"""
Shared EWA data transformation helpers.

This module consolidates logic that was previously duplicated across
markdown_utils.py and html_utils.py.
"""

from typing import Any, Dict, List, Optional
import html as html_module


def to_title_case(text: str) -> str:
    """
    Convert text to title case, handling special cases.
    
    Args:
        text: The text to convert
        
    Returns:
        Title-cased text
    """
    if not text:
        return text
    
    # Words that should remain lowercase (unless first word)
    lowercase_words = {"a", "an", "the", "and", "but", "or", "for", "nor", "on", "at", "to", "by", "of", "in"}
    
    words = text.split()
    result = []
    
    for i, word in enumerate(words):
        if i == 0 or word.lower() not in lowercase_words:
            result.append(word.capitalize())
        else:
            result.append(word.lower())
    
    return " ".join(result)


def escape_html(text: str) -> str:
    """
    Escape HTML special characters in text.
    
    Args:
        text: The text to escape
        
    Returns:
        HTML-escaped text
    """
    if not text:
        return ""
    return html_module.escape(str(text))


def merge_findings_and_recommendations(
    findings: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge Key Findings with their linked Recommendations.
    
    Each finding is enriched with its linked recommendation data.
    
    Args:
        findings: List of finding dictionaries
        recommendations: List of recommendation dictionaries
        
    Returns:
        List of merged finding dictionaries with recommendation data
    """
    # Build a lookup map: Issue ID -> Recommendation
    rec_by_issue_id: Dict[str, Dict[str, Any]] = {}
    for rec in recommendations:
        linked_id = rec.get("Linked Issue ID") or rec.get("Linked issue ID") or ""
        if linked_id:
            rec_by_issue_id[linked_id] = rec
    
    merged = []
    for finding in findings:
        issue_id = finding.get("Issue ID") or ""
        merged_item = dict(finding)
        
        # Find linked recommendation
        rec = rec_by_issue_id.get(issue_id)
        if rec:
            # Add recommendation fields to the finding
            merged_item["Recommendation ID"] = rec.get("Recommendation ID", "")
            merged_item["Action"] = rec.get("Action", "")
            merged_item["Preventative Action"] = rec.get("Preventative Action", "")
            merged_item["Responsible Area"] = rec.get("Responsible Area", "")
            merged_item["Estimated Effort"] = rec.get("Estimated Effort", {})
        
        merged.append(merged_item)
    
    return merged


def normalize_severity(severity: str) -> str:
    """
    Normalize severity string to lowercase.
    
    Args:
        severity: The severity string
        
    Returns:
        Lowercase severity string
    """
    if not severity:
        return "medium"
    return severity.lower().strip()


def get_severity_color(severity: str) -> str:
    """
    Get the color associated with a severity level.
    
    Args:
        severity: The severity level (critical, high, medium, low)
        
    Returns:
        Color string for the severity
    """
    severity = normalize_severity(severity)
    colors = {
        "critical": "#dc3545",  # Red
        "high": "#fd7e14",      # Orange
        "medium": "#ffc107",    # Yellow
        "low": "#28a745",       # Green
    }
    return colors.get(severity, "#6c757d")  # Gray default


def format_effort(effort: Any) -> str:
    """
    Format the Estimated Effort field for display.
    
    Args:
        effort: Either a string or dict with analysis/implementation keys
        
    Returns:
        Formatted effort string
    """
    if not effort:
        return ""
    
    if isinstance(effort, dict):
        analysis = effort.get("analysis") or effort.get("Analysis", "")
        implementation = effort.get("implementation") or effort.get("Implementation", "")
        if analysis and implementation:
            return f"Analysis: {analysis}, Implementation: {implementation}"
        elif analysis:
            return f"Analysis: {analysis}"
        elif implementation:
            return f"Implementation: {implementation}"
        return ""
    
    return str(effort)
