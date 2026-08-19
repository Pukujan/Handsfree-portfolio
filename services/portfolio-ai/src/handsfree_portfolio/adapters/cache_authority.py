from __future__ import annotations

import hashlib
import json
from typing import Any

from fossil_core.domain.pack import PackAccess


class FossilPackAuthorityFingerprint:
    """Hashes mounted durable events so lifecycle/redaction changes change cache eligibility."""

    def __init__(self, *, event_store: Any, access: PackAccess) -> None:
        self.event_store = event_store
        self.access = access

    def fingerprint(self) -> str:
        events = []
        for event in self.event_store.iter_events():
            pack_id = str(event["pack_id"])
            self.access.require_read(pack_id)
            events.append(event)
        events.sort(key=lambda item: (str(item["recorded_at"]), str(item["event_id"])))
        canonical = json.dumps(
            {
                "mountedPacks": sorted(self.access.read_mounts),
                "events": events,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
