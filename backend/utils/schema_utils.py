"""
Schema version detection utilities for EWA analysis JSON.

Supports both v1.1 (flat) and v2.0 (pillar-based) schema formats.
"""

from __future__ import annotations

from typing import Any, Dict


def detect_schema_version(data: Dict[str, Any]) -> str:
    """Return the schema version string from an EWA JSON dict.

    Falls back to ``"1.1"`` when the field is missing (pre-v2 data).
    """
    return str(data.get("Schema Version", "1.1"))


def is_pillar_schema(data: Dict[str, Any]) -> bool:
    """Return True if *data* uses the v2.0 pillar-based schema."""
    return detect_schema_version(data).startswith("2.")
