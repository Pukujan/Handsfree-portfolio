from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SupportState = Literal["supported", "uncertain", "unsupported"]


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source_ref: str
    label: str


@dataclass(frozen=True)
class SupportedClaim:
    claim_id: str
    proposition: str
    support: SupportState
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnswerPlan:
    turn_id: str
    generation: int
    dialogue_act: str
    claims: tuple[SupportedClaim, ...]
    evidence: tuple[EvidenceRef, ...]


@dataclass(frozen=True)
class RenderedAnswer:
    turn_id: str
    generation: int
    text: str
    evidence: tuple[EvidenceRef, ...]
