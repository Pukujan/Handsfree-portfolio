from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from fossil_core.domain.lifecycle import KnowledgeState

from handsfree_portfolio.adapters.fossil_pack import FossilPackWorkspace, FossilSchemaRoot, PUBLIC_PACK_ID, ingest_supported_claim

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"


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

        receipts = []
        for index, claim in enumerate(claims):
            receipts.append(
                ingest_supported_claim(
                    workspace,
                    policy_path=pack_root / "source-policy.json",
                    claim=claim,
                    observed_at=f"2026-08-19T20:10:{index:02d}Z",
                )
            )

        events = sorted(
            workspace.event_store.iter_events(),
            key=lambda event: (event["recorded_at"], event["event_id"]),
        )
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
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
