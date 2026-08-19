from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from fossil_core import KnowledgePackValidator
from fossil_core.adapters.filesystem import ArtifactStore, DurableEventStore
from fossil_core.domain.pack import PackAccess
from fossil_core.source import SourceSnapshotStore

from handsfree_portfolio.adapters.public_source import exact_anchor_span, fetch_exact_public_source, load_source_policy

PUBLIC_PACK_ID = "pack_c70aedc3a5bc7600399f22808f4a8de0"
PUBLIC_PACK_ALIAS = "portfolio-public"


@dataclass(frozen=True)
class FossilSchemaRoot:
    root: Path

    @property
    def pack(self) -> Path:
        return self.root / "knowledge-pack" / "v1.schema.json"

    @property
    def events(self) -> Path:
        return self.root / "events" / "v1.schema.json"

    @property
    def source_snapshot(self) -> Path:
        return self.root / "source-snapshot" / "v1.schema.json"

    @property
    def citation(self) -> Path:
        return self.root / "citation" / "v1.schema.json"


@dataclass
class FossilPackWorkspace:
    pack_root: Path
    schemas: FossilSchemaRoot

    def __post_init__(self) -> None:
        self.pack_root = Path(self.pack_root)
        self.pack_root.mkdir(parents=True, exist_ok=True)
        self.artifact_store = ArtifactStore(self.pack_root / "artifacts")
        self.source_store = SourceSnapshotStore(
            self.pack_root / "sources",
            self.artifact_store,
            self.schemas.source_snapshot,
            self.schemas.citation,
        )
        self.event_store = DurableEventStore(self.pack_root / "events", self.schemas.events)
        self.pack_validator = KnowledgePackValidator(self.schemas.pack)

    def load_manifest(self) -> dict[str, Any]:
        manifest = json.loads((self.pack_root / "manifest.json").read_text(encoding="utf-8"))
        self.pack_validator.validate(manifest)
        if manifest["pack_id"] != PUBLIC_PACK_ID:
            raise ValueError("unexpected public portfolio pack identity")
        return manifest

    def refresh_artifact_manifest_index(self) -> None:
        index_path = self.pack_root / "artifacts" / "manifest.jsonl"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        manifests_root = self.pack_root / "artifacts" / "manifests"
        manifests = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(manifests_root.glob("*/*.json"))]
        index_path.write_text(
            "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in manifests),
            encoding="utf-8",
        )


def public_runtime_access() -> PackAccess:
    return PackAccess(pack_id=PUBLIC_PACK_ID, read_mounts=frozenset({PUBLIC_PACK_ID}), write_targets=frozenset())


def operator_access(manifest: Mapping[str, Any]) -> PackAccess:
    access = PackAccess.from_manifest(dict(manifest))
    if access.pack_id != PUBLIC_PACK_ID:
        raise ValueError("operator access must target the public portfolio pack")
    return access


def _plus_microsecond(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(microseconds=1)).astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _base_event(*, event_type: str, claim_id: str, occurred_at: str, recorded_at: str, correlation_id: str) -> dict[str, Any]:
    return {
        "schema_version": "dkg.event.v1",
        "event_type": event_type,
        "occurred_at": occurred_at,
        "recorded_at": recorded_at,
        "pack_id": PUBLIC_PACK_ID,
        "actor": {"actor_type": "system", "actor_id": "handsfree-portfolio-curation-v1"},
        "subject_refs": [claim_id],
        "correlation_id": correlation_id,
        "caused_by_event_ids": [],
        "evidence_refs": [],
        "source_snapshot_refs": [],
        "payload": {},
        "provenance": {
            "method": "reviewed_public_source_curation",
            "prompt_or_policy_ref": "knowledge/portfolio-public/source-policy.json",
            "benchmark_ref": "handsfree-slice1-fossil-review-v1",
        },
    }


def ingest_supported_claim(
    workspace: FossilPackWorkspace,
    *,
    policy_path: Path,
    claim: Mapping[str, Any],
    observed_at: str,
    opener=None,
) -> dict[str, Any]:
    manifest = workspace.load_manifest()
    operator_access(manifest).require_write(PUBLIC_PACK_ID)

    source_spec = dict(claim["source"])
    source = fetch_exact_public_source(
        load_source_policy(policy_path),
        repository=source_spec["repository"],
        revision=source_spec["revision"],
        path=source_spec["path"],
        opener=opener,
    )
    byte_start, byte_end = exact_anchor_span(source.data, source_spec["anchorText"])

    snapshot = workspace.source_store.put_snapshot(
        source.data,
        locator={"repository_ref": source.repository_ref},
        retrieved_at=observed_at,
        source_role="primary",
        quality={
            "authority": None,
            "directness": None,
            "independence": None,
            "reproducibility": None,
            "timeliness": None,
            "notes": "Primary public project repository source; quality remains claim-specific.",
        },
        version_metadata={"commit_sha": source.revision},
        media_type="text/plain",
    )
    citation = workspace.source_store.create_citation(snapshot["snapshot_id"], byte_start=byte_start, byte_end=byte_end)

    claim_id = str(claim["claimId"])
    correlation_id = f"slice1:{claim_id}"
    proposed = _base_event(
        event_type="claim.proposed", claim_id=claim_id, occurred_at=observed_at, recorded_at=observed_at, correlation_id=correlation_id
    )
    proposed.update(
        {
            "idempotency_key": f"slice1:{claim_id}:proposed:{source.revision}",
            "evidence_refs": [snapshot["artifact_id"]],
            "source_snapshot_refs": [snapshot["snapshot_id"]],
            "payload": {"claim_text": claim["claimText"], "citation": citation},
        }
    )
    proposed_committed = workspace.event_store.commit(proposed)

    supported = _base_event(
        event_type="claim.state_changed",
        claim_id=claim_id,
        occurred_at=observed_at,
        recorded_at=_plus_microsecond(observed_at),
        correlation_id=correlation_id,
    )
    supported.update(
        {
            "caused_by_event_ids": [proposed_committed["event_id"]],
            "idempotency_key": f"slice1:{claim_id}:supported:{source.revision}",
            "evidence_refs": [snapshot["artifact_id"]],
            "source_snapshot_refs": [snapshot["snapshot_id"]],
            "payload": {
                "citation": citation,
                "from_state": "proposed",
                "to_state": "supported",
                "review_ref": "handsfree-slice1-fossil-review-v1",
            },
        }
    )
    supported_committed = workspace.event_store.commit(supported)
    workspace.refresh_artifact_manifest_index()
    resolved = workspace.source_store.resolve_citation(citation, allowed_source_roles={"primary"})
    return {
        "claim_id": claim_id,
        "proposal_event_id": proposed_committed["event_id"],
        "supported_event_id": supported_committed["event_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "artifact_id": snapshot["artifact_id"],
        "citation": citation,
        "resolved_text": resolved["text"],
    }
