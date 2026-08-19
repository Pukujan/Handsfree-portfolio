from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from fossil_core.domain.lifecycle import KnowledgeState

from handsfree_portfolio.adapters.fossil_pack import FossilPackWorkspace, FossilSchemaRoot, PUBLIC_PACK_ID, ingest_supported_claim
from handsfree_portfolio.adapters.neo4j_projection import Neo4jClaimProjectionAdapter

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
OBSERVED_AT = "2026-08-19T20:10:00Z"


def connect_projection() -> Neo4jClaimProjectionAdapter:
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")
    if not uri or not user or not password:
        raise SystemExit("NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD are required")
    last_error: Exception | None = None
    for _ in range(30):
        projection = Neo4jClaimProjectionAdapter(uri=uri, user=user, password=password)
        try:
            projection.verify_connectivity()
            return projection
        except Exception as exc:
            last_error = exc
            projection.close()
            time.sleep(2)
    raise SystemExit(f"Neo4j did not become ready: {last_error}")


def main() -> None:
    schema_root = os.environ.get("FOSSIL_SCHEMA_ROOT")
    if not schema_root:
        raise SystemExit("FOSSIL_SCHEMA_ROOT is required")

    document = json.loads((KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8"))
    claims = document["claims"]

    with tempfile.TemporaryDirectory(prefix="handsfree-g1-") as directory:
        pack_root = Path(directory) / "portfolio-public"
        pack_root.mkdir()
        shutil.copy(KNOWLEDGE / "manifest.json", pack_root / "manifest.json")
        shutil.copy(KNOWLEDGE / "source-policy.json", pack_root / "source-policy.json")
        workspace = FossilPackWorkspace(pack_root, FossilSchemaRoot(Path(schema_root)))

        receipts = [
            ingest_supported_claim(
                workspace,
                policy_path=pack_root / "source-policy.json",
                claim=claim,
                observed_at=OBSERVED_AT,
            )
            for claim in claims
        ]

        events = sorted(workspace.event_store.iter_events(), key=lambda event: (event["recorded_at"], event["event_id"]))
        state = KnowledgeState.replay(events)

        expected_claims = {claim["claimId"] for claim in claims}
        if set(state.claims) != expected_claims:
            raise SystemExit("G1 live verification reconstructed an unexpected claim set")
        if any(state.claims[claim_id] != "supported" for claim_id in expected_claims):
            raise SystemExit("G1 live verification did not reconstruct all claims as supported")
        if len(events) != len(claims) * 2:
            raise SystemExit("G1 live verification expected proposal + support event per claim")
        if any(event["pack_id"] != PUBLIC_PACK_ID for event in events):
            raise SystemExit("G1 live verification observed an event outside the public pack")
        if any(receipt["resolved_text"] != claim["source"]["anchorText"] for receipt, claim in zip(receipts, claims, strict=True)):
            raise SystemExit("G1 live verification citation did not resolve to exact anchor text")

        projection = connect_projection()
        try:
            first_receipts = projection.rebuild(events_root=workspace.event_store.root)
            if any(receipt.status != "applied" for receipt in first_receipts):
                raise SystemExit(f"first Neo4j rebuild failed: {first_receipts}")
            first_snapshot = projection.semantic_snapshot()
            first_digest = projection.semantic_digest()
            if {item["stable_id"] for item in first_snapshot} != expected_claims:
                raise SystemExit("Neo4j projection claim identity differs from FOSSIL durable identities")
            if any(item["state"] != "supported" for item in first_snapshot):
                raise SystemExit("Neo4j projection did not reconstruct supported claim state")

            projection.clear()
            if projection.semantic_snapshot() != []:
                raise SystemExit("destructive Neo4j reset did not clear projection")

            second_receipts = projection.rebuild(events_root=workspace.event_store.root)
            if any(receipt.status != "applied" for receipt in second_receipts):
                raise SystemExit(f"second Neo4j rebuild failed: {second_receipts}")
            second_digest = projection.semantic_digest()
            if second_digest != first_digest:
                raise SystemExit("destructive Neo4j rebuild changed semantic digest")
        finally:
            projection.close()

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "authority": "verification_receipt_only",
                    "pack_id": PUBLIC_PACK_ID,
                    "claim_count": len(claims),
                    "event_count": len(events),
                    "snapshot_count": len({receipt["snapshot_id"] for receipt in receipts}),
                    "all_claims_supported_after_replay": True,
                    "all_citations_resolved_exact_bytes": True,
                    "neo4j_destructive_rebuild_pass": True,
                    "neo4j_semantic_digest": first_digest,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
