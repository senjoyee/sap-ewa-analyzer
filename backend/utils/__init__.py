"""Utility modules for the EWA Analyzer backend."""

from utils.date_utils import parse_date_any, format_date_display, format_date_iso
from utils.ewa_helpers import (
    to_title_case,
    escape_html,
    merge_findings_and_recommendations,
    normalize_severity,
    get_severity_color,
    format_effort,
)

__all__ = [
    # date_utils
    "parse_date_any",
    "format_date_display",
    "format_date_iso",
    # ewa_helpers
    "to_title_case",
    "escape_html",
    "merge_findings_and_recommendations",
    "normalize_severity",
    "get_severity_color",
    "format_effort",
]