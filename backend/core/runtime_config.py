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


def _get_float(name: str, default: Optional[float]) -> Optional[float]:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in allowed:
        return normalized
    return default


CHAT_HISTORY_LIMIT = _get_int("CHAT_HISTORY_LIMIT", 10)
CHAT_MAX_OUTPUT_TOKENS = _get_int("CHAT_MAX_OUTPUT_TOKENS", 4096)
SUMMARY_MAX_OUTPUT_TOKENS = _get_int("SUMMARY_MAX_OUTPUT_TOKENS", 32768)
PARAM_MAX_OUTPUT_TOKENS = _get_int("PARAM_MAX_OUTPUT_TOKENS", 65536)
ANTHROPIC_MAX_OUTPUT_TOKENS = _get_int("ANTHROPIC_MAX_OUTPUT_TOKENS", 32768)
ANTHROPIC_TIMEOUT_SECONDS = _get_int("ANTHROPIC_TIMEOUT_SECONDS", 1800)
ANTHROPIC_CONNECT_TIMEOUT_SECONDS = _get_int("ANTHROPIC_CONNECT_TIMEOUT_SECONDS", 30)
ANTHROPIC_THINKING_BUDGET_TOKENS = _get_int("ANTHROPIC_THINKING_BUDGET_TOKENS", 0) # 0 means disabled
ANTHROPIC_TEMPERATURE: Optional[float] = _get_float("ANTHROPIC_TEMPERATURE", None)
PDF_METADATA_TEXT_LIMIT = _get_int("PDF_METADATA_TEXT_LIMIT", 4000)
PDF_METADATA_MAX_TOKENS = _get_int("PDF_METADATA_MAX_TOKENS", 100)
SUMMARY_REASONING_EFFORT = _get_choice("SUMMARY_REASONING_EFFORT", "none", {"minimal", "none", "low", "medium", "high", "xhigh"})
PARAM_REASONING_EFFORT = _get_choice("PARAM_REASONING_EFFORT", "none", {"minimal", "none", "low", "medium", "high", "xhigh"})

# V2 agentic pipeline model deployments
V2_ROUTER_MODEL = os.getenv("V2_ROUTER_MODEL", "gpt-5.4-nano")
V2_SPECIALIST_MODEL = os.getenv("V2_SPECIALIST_MODEL", "gpt-5.4-mini")
V2_DEEP_MODEL = os.getenv("V2_DEEP_MODEL", "gpt-5.4")
V2_SPECIALIST_MAX_TOKENS = _get_int("V2_SPECIALIST_MAX_TOKENS", 16384)
V2_DEEP_MAX_TOKENS = _get_int("V2_DEEP_MAX_TOKENS", 16384)
V2_SPECIALIST_REASONING = _get_choice("V2_SPECIALIST_REASONING", "none", {"minimal", "none", "low", "medium", "high", "xhigh"})
V2_DEEP_REASONING = _get_choice("V2_DEEP_REASONING", "medium", {"minimal", "none", "low", "medium", "high", "xhigh"})

# V2 agentic pipeline — Anthropic model names (used when PROVIDER=anthropic)
V2_ANTHROPIC_ROUTER_MODEL = os.getenv("V2_ANTHROPIC_ROUTER_MODEL", "claude-haiku-4.5")
V2_ANTHROPIC_SPECIALIST_MODEL = os.getenv("V2_ANTHROPIC_SPECIALIST_MODEL", "claude-haiku-4.5")
V2_ANTHROPIC_DEEP_MODEL = os.getenv("V2_ANTHROPIC_DEEP_MODEL", "claude-sonnet-4.6")
V2_ANTHROPIC_SPECIALIST_MAX_TOKENS = _get_int("V2_ANTHROPIC_SPECIALIST_MAX_TOKENS", 16384)
V2_ANTHROPIC_DEEP_MAX_TOKENS = _get_int("V2_ANTHROPIC_DEEP_MAX_TOKENS", 16384)
