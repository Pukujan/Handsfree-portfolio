from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicClaimRecord:
    claim_id: str
    proposition: str
    evidence_ids: tuple[str, ...]
    snapshot_ids: tuple[str, ...]
    citation_id: str
    source_ref: str
    cited_text: str


__all__ = ["PublicClaimRecord"]
