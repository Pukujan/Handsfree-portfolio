from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from threading import RLock

from handsfree_portfolio.domain.cache import CachedAnswerArtifact, CacheMetricsSnapshot


class InMemoryAnswerCache:
    """Process-local LRU cache for derived answer artifacts; never a truth store."""

    def __init__(self, max_entries: int = 256) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries: OrderedDict[str, CachedAnswerArtifact] = OrderedDict()
        self._lock = RLock()
        self._metrics = CacheMetricsSnapshot()

    def _bump(self, **changes: int) -> None:
        values = self._metrics.__dict__ | {
            key: getattr(self._metrics, key) + delta
            for key, delta in changes.items()
        }
        self._metrics = CacheMetricsSnapshot(**values)

    def get(self, key: str) -> CachedAnswerArtifact | None:
        with self._lock:
            self._bump(lookups=1)
            value = self._entries.get(key)
            if value is None:
                self._bump(misses=1)
                return None
            self._entries.move_to_end(key)
            self._bump(hits=1)
            return value

    def put(self, key: str, answer: CachedAnswerArtifact) -> None:
        with self._lock:
            self._entries[key] = answer
            self._entries.move_to_end(key)
            self._bump(writes=1)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
                self._bump(evictions=1)

    def delete(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def mark_validated_hit(self) -> None:
        with self._lock:
            self._bump(validated_hits=1)

    def mark_stale_rejection(self) -> None:
        with self._lock:
            self._bump(stale_rejections=1)

    def mark_outage(self) -> None:
        with self._lock:
            self._bump(outages=1)

    def mark_false_hit(self) -> None:
        with self._lock:
            self._bump(false_hit_incidents=1)

    def snapshot_metrics(self) -> CacheMetricsSnapshot:
        with self._lock:
            return replace(self._metrics)

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._entries.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
