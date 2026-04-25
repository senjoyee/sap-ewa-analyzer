"""
CostTracker — accumulates token usage per phase and model, calculates cost,
and saves a _cost.json report alongside the other output artifacts.
"""

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class _Entry:
    phase: str
    model: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class CostTracker:
    """Accumulate token usage across all pipeline phases and calculate cost."""

    def __init__(self, pricing: dict[str, dict[str, float]]):
        """
        pricing: {deployment_name: {"input_per_1m": float, "output_per_1m": float}}
        """
        self.pricing = pricing
        self._entries: dict[str, _Entry] = {}  # keyed by phase name
        self._lock = threading.Lock()

    def record(self, phase: str, model: str, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            if phase not in self._entries:
                self._entries[phase] = _Entry(phase=phase, model=model)
            e = self._entries[phase]
            e.calls += 1
            e.input_tokens += input_tokens
            e.output_tokens += output_tokens

    def _cost(self, model: str, input_tokens: int, output_tokens: int) -> tuple[float, float]:
        p = self.pricing.get(model, {})
        inp_cost = input_tokens / 1_000_000 * p.get("input_per_1m", 0.0)
        out_cost = output_tokens / 1_000_000 * p.get("output_per_1m", 0.0)
        return inp_cost, out_cost

    def to_dict(self, pdf_name: str = "") -> dict:
        breakdown = []
        total_calls = total_inp = total_out = 0
        total_cost = 0.0

        for e in self._entries.values():
            inp_cost, out_cost = self._cost(e.model, e.input_tokens, e.output_tokens)
            entry_cost = inp_cost + out_cost
            breakdown.append({
                "phase": e.phase,
                "model": e.model,
                "calls": e.calls,
                "input_tokens": e.input_tokens,
                "output_tokens": e.output_tokens,
                "input_cost_usd": round(inp_cost, 6),
                "output_cost_usd": round(out_cost, 6),
                "total_cost_usd": round(entry_cost, 6),
            })
            total_calls += e.calls
            total_inp += e.input_tokens
            total_out += e.output_tokens
            total_cost += entry_cost

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pdf": pdf_name,
            "breakdown": breakdown,
            "totals": {
                "calls": total_calls,
                "input_tokens": total_inp,
                "output_tokens": total_out,
                "total_tokens": total_inp + total_out,
                "cost_usd": round(total_cost, 6),
            },
            "notes": [
                "Phase 0 (PageIndex / gpt-5.4-nano) not tracked — runs via LiteLLM",
                "Prices from config.yaml pricing section — update if Azure rates change",
            ],
        }

    def save(self, path: Path, pdf_name: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(pdf_name), indent=2), encoding="utf-8")
