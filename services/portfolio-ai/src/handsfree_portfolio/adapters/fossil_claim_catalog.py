from __future__ import annotations

from typing import Any

from fossil_core.domain.lifecycle import KnowledgeState
from fossil_core.domain.pack import PackAccess

from handsfree_portfolio.domain.knowledge import PublicClaimRecord


class FossilClaimCatalog:
    """Read-only supported-claim view over authoritative FOSSIL durable state."""

    def __init__(self, *, event_store: Any, source_store: Any, access: PackAccess) -> None:
        self.event_store = event_store
        self.source_store = source_store
        self.access = access

    def _events(self) -> list[dict[str, Any]]:
        events = []
        for event in self.event_store.iter_events():
            self.access.require_read(str(event["pack_id"]))
            events.append(event)
        return sorted(events, key=lambda event: (event["recorded_at"], event["event_id"]))

    def all_supported(self) -> tuple[PublicClaimRecord, ...]:
        events = self._events()
        state = KnowledgeState.replay(events)
        proposals = {
            str(event["subject_refs"][0]): event
            for event in events
            if event["event_type"] == "claim.proposed"
        }
        latest_state_events: dict[str, dict[str, Any]] = {}
        for event in events:
            if event["event_type"] == "claim.state_changed":
                latest_state_events[str(event["subject_refs"][0])] = event

        records = []
        for claim_id in sorted(state.claims):
            if state.claims[claim_id] != "supported":
                continue
            proposal = proposals[claim_id]
            state_event = latest_state_events[claim_id]
            citation = state_event["payload"]["citation"]
            resolved = self.source_store.resolve_citation(citation, allowed_source_roles={"primary"})
            snapshot = resolved["snapshot"]
            locator = snapshot["locator"]
            source_ref = locator.get("repository_ref") or locator.get("url") or locator.get("identifier")
            if not source_ref:
                raise ValueError(f"supported claim {claim_id} has no resolvable public source locator")
            if not state_event.get("evidence_refs") or not state_event.get("source_snapshot_refs"):
                raise ValueError(f"supported claim {claim_id} is missing durable evidence references")
            records.append(
                PublicClaimRecord(
                    claim_id=claim_id,
                    proposition=str(proposal["payload"]["claim_text"]),
                    evidence_ids=tuple(str(value) for value in state_event["evidence_refs"]),
                    snapshot_ids=tuple(str(value) for value in state_event["source_snapshot_refs"]),
                    citation_id=str(citation["citation_id"]),
                    source_ref=str(source_ref),
                    cited_text=str(resolved["text"] or ""),
                )
            )
        return tuple(records)

    def get(self, claim_id: str) -> PublicClaimRecord:
        for record in self.all_supported():
            if record.claim_id == claim_id:
                return record
        raise KeyError(claim_id)
