from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    def now_rfc3339(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class SequenceClock:
    """Deterministic test clock with monotonic microsecond stamps."""

    def __init__(self, values: list[str]) -> None:
        if not values:
            raise ValueError("SequenceClock needs at least one timestamp")
        self._values = list(values)
        self._index = 0

    def now_rfc3339(self) -> str:
        value = self._values[min(self._index, len(self._values) - 1)]
        self._index += 1
        return value
