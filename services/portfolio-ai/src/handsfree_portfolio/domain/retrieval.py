from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RetrievalLane = Literal["exact", "sparse-semantic", "abstain"]


@dataclass(frozen=True)
class RetrievalCandidate:
    claim_id: str
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    lane: RetrievalLane
    candidates: tuple[RetrievalCandidate, ...]

    @property
    def claim_ids(self) -> tuple[str, ...]:
        return tuple(candidate.claim_id for candidate in self.candidates)

    @property
    def abstained(self) -> bool:
        return not self.candidates


@dataclass(frozen=True)
class GraphEvidencePath:
    claim_id: str
    evidence_ids: tuple[str, ...]
    snapshot_ids: tuple[str, ...]


__all__ = ["GraphEvidencePath", "RetrievalCandidate", "RetrievalLane", "RetrievalResult"]
