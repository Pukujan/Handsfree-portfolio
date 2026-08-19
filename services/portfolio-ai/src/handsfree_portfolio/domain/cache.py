from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CachedAnswerArtifact:
    """Derived answer material only; never canonical knowledge or a reusable turn identity."""

    text: str
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class CacheMetricsSnapshot:
    lookups: int = 0
    hits: int = 0
    validated_hits: int = 0
    misses: int = 0
    stale_rejections: int = 0
    outages: int = 0
    writes: int = 0
    evictions: int = 0
    false_hit_incidents: int = 0

    @property
    def hit_rate(self) -> float:
        return self.hits / self.lookups if self.lookups else 0.0

    @property
    def validated_hit_rate(self) -> float:
        return self.validated_hits / self.lookups if self.lookups else 0.0
