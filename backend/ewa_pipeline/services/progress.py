from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class ProgressEvent:
    stage: str
    status: str
    label: str
    detail: str = ""
    current: int | None = None
    total: int | None = None
    percent: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.percent is None and self.current is not None and self.total:
            payload["percent"] = round((self.current / self.total) * 100, 2)
        return payload


ProgressCallback = Callable[[ProgressEvent], None]


class ProgressReporter:
    def __init__(self, callback: ProgressCallback | None = None):
        self._callback = callback

    def emit(
        self,
        stage: str,
        status: str,
        label: str,
        detail: str = "",
        current: int | None = None,
        total: int | None = None,
        percent: float | None = None,
    ) -> ProgressEvent:
        event = ProgressEvent(
            stage=stage,
            status=status,
            label=label,
            detail=detail,
            current=current,
            total=total,
            percent=percent,
        )
        if self._callback:
            self._callback(event)
        return event
