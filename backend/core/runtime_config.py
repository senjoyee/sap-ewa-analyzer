"""Runtime configuration loaded from environment with defaults."""
from __future__ import annotations

import os
from typing import Optional


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


CHAT_HISTORY_LIMIT = _get_int("CHAT_HISTORY_LIMIT", 10)
CHAT_MAX_OUTPUT_TOKENS = _get_int("CHAT_MAX_OUTPUT_TOKENS", 4096)
SUMMARY_MAX_OUTPUT_TOKENS = _get_int("SUMMARY_MAX_OUTPUT_TOKENS", 32768)
PARAM_MAX_OUTPUT_TOKENS = _get_int("PARAM_MAX_OUTPUT_TOKENS", 16384)
ANTHROPIC_MAX_OUTPUT_TOKENS = _get_int("ANTHROPIC_MAX_OUTPUT_TOKENS", 32768)
ANTHROPIC_TIMEOUT_SECONDS = _get_int("ANTHROPIC_TIMEOUT_SECONDS", 1800)
ANTHROPIC_CONNECT_TIMEOUT_SECONDS = _get_int("ANTHROPIC_CONNECT_TIMEOUT_SECONDS", 30)
PDF_METADATA_TEXT_LIMIT = _get_int("PDF_METADATA_TEXT_LIMIT", 4000)
PDF_METADATA_MAX_TOKENS = _get_int("PDF_METADATA_MAX_TOKENS", 100)
