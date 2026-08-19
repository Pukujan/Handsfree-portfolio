from __future__ import annotations

from handsfree_portfolio.adapters.cache_authority import FossilPackAuthorityFingerprint

PACK_ID = "pack_c70aedc3a5bc7600399f22808f4a8de0"


class FakeAccess:
    read_mounts = frozenset({PACK_ID})

    def require_read(self, pack_id: str) -> None:
        if pack_id not in self.read_mounts:
            raise PermissionError(pack_id)


class FakeStore:
    def __init__(self, *, events=(), redactions=()) -> None:
        self.events = tuple(events)
        self.redactions = tuple(redactions)

    def iter_events(self):
        return iter(self.events)

    def iter_redactions(self):
        return iter(self.redactions)


def test_redaction_tombstone_changes_authority_even_when_live_event_set_is_empty() -> None:
    access = FakeAccess()
    before = FossilPackAuthorityFingerprint(event_store=FakeStore(), access=access).fingerprint()
    tombstone = {
        "event_id": "evt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "pack_id": PACK_ID,
        "event_type": "claim.state_changed",
        "reason": "privacy erasure",
        "authority": "data-controller",
        "redacted_at": "2026-08-19T21:36:00Z",
        "request_ref": "erase-001",
        "canonical_hash": {"algorithm": "sha256", "digest": "b" * 64},
    }
    after = FossilPackAuthorityFingerprint(
        event_store=FakeStore(redactions=(tombstone,)),
        access=access,
    ).fingerprint()
    assert before != after


def test_redaction_order_does_not_change_authority_digest() -> None:
    access = FakeAccess()
    first = {
        "event_id": "evt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "pack_id": PACK_ID,
        "event_type": "claim.proposed",
        "reason": "privacy erasure",
        "authority": "data-controller",
        "redacted_at": "2026-08-19T21:36:00Z",
        "canonical_hash": {"algorithm": "sha256", "digest": "a" * 64},
    }
    second = {
        "event_id": "evt_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "pack_id": PACK_ID,
        "event_type": "claim.state_changed",
        "reason": "privacy erasure",
        "authority": "data-controller",
        "redacted_at": "2026-08-19T21:37:00Z",
        "canonical_hash": {"algorithm": "sha256", "digest": "b" * 64},
    }
    left = FossilPackAuthorityFingerprint(event_store=FakeStore(redactions=(first, second)), access=access).fingerprint()
    right = FossilPackAuthorityFingerprint(event_store=FakeStore(redactions=(second, first)), access=access).fingerprint()
    assert left == right
