from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from handsfree_portfolio.adapters.clock import SystemClock
from handsfree_portfolio.adapters.fossil_claim_catalog import FossilClaimCatalog
from handsfree_portfolio.adapters.fossil_pack import FossilPackWorkspace, FossilSchemaRoot, PUBLIC_PACK_ID, ingest_supported_claim, public_runtime_access
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy
from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions
from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.application.grounded_rendering import ABSTENTION_TEXT, ClaimBoundTemplateRenderer, DeterministicGroundingVerifier
from handsfree_portfolio.application.retrieval import PublicClaimRetriever

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
SCHEMAS = ROOT / "contracts" / "schemas"
OBSERVED_AT = "2026-08-19T20:45:00Z"


def validate_events(events, state) -> None:
    turn_validator = Draft202012Validator(
        json.loads((SCHEMAS / "turn-event-v1.schema.json").read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )
    answer_validator = Draft202012Validator(
        json.loads((SCHEMAS / "portfolio-answer-v1.schema.json").read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )
    state_validator = Draft202012Validator(
        json.loads((SCHEMAS / "conversation-state-v1.schema.json").read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )
    for event in events:
        turn_validator.validate(event.to_contract())
        if event.type == "answer.planned":
            answer_validator.validate(event.payload)
    state_validator.validate(state.to_contract())


def event(events, event_type: str):
    return next(item for item in events if item.type == event_type)


def supersede_claim(workspace: FossilPackWorkspace, claim_id: str) -> None:
    prior = next(
        item
        for item in workspace.event_store.iter_events()
        if item["event_type"] == "claim.state_changed" and item["subject_refs"] == [claim_id]
    )
    workspace.event_store.commit(
        {
            "schema_version": "dkg.event.v1",
            "event_type": "claim.state_changed",
            "occurred_at": "2026-08-19T20:46:00Z",
            "recorded_at": "2026-08-19T20:46:00.000000Z",
            "pack_id": PUBLIC_PACK_ID,
            "actor": {"actor_type": "system", "actor_id": "handsfree-g3-live-verifier"},
            "subject_refs": [claim_id],
            "correlation_id": f"g3-supersede:{claim_id}",
            "caused_by_event_ids": [prior["event_id"]],
            "evidence_refs": list(prior["evidence_refs"]),
            "source_snapshot_refs": list(prior["source_snapshot_refs"]),
            "idempotency_key": f"g3-supersede:{claim_id}:v1",
            "payload": {
                "from_state": "supported",
                "to_state": "superseded",
                "reason": "G3 lifecycle verification fixture",
                "citation": prior["payload"]["citation"],
            },
            "provenance": {
                "method": "g3_live_lifecycle_verification",
                "prompt_or_policy_ref": "docs/DEVELOPMENT-METHOD.md",
                "benchmark_ref": "g3-live-v1",
            },
        }
    )


def main() -> None:
    schema_root = os.environ.get("FOSSIL_SCHEMA_ROOT")
    if not schema_root:
        raise SystemExit("FOSSIL_SCHEMA_ROOT is required")

    claims = json.loads((KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8"))["claims"]

    with tempfile.TemporaryDirectory(prefix="handsfree-g3-") as directory:
        pack_root = Path(directory) / "portfolio-public"
        pack_root.mkdir()
        for filename in ("manifest.json", "source-policy.json", "retrieval-v1.json"):
            shutil.copy(KNOWLEDGE / filename, pack_root / filename)
        workspace = FossilPackWorkspace(pack_root, FossilSchemaRoot(Path(schema_root)))
        for claim in claims:
            ingest_supported_claim(
                workspace,
                policy_path=pack_root / "source-policy.json",
                claim=claim,
                observed_at=OBSERVED_AT,
            )

        catalog = FossilClaimCatalog(
            event_store=workspace.event_store,
            source_store=workspace.source_store,
            access=public_runtime_access(),
        )
        sessions = InMemoryConversationSessions()
        kernel = ConversationKernel(
            catalog=catalog,
            retriever=PublicClaimRetriever(catalog, load_retrieval_policy(pack_root / "retrieval-v1.json")),
            sessions=sessions,
            renderer=ClaimBoundTemplateRenderer(),
            verifier=DeterministicGroundingVerifier(),
            clock=SystemClock(),
        )

        start = time.perf_counter_ns()
        first = list(kernel.stream_turn(conversation_id="live", question="What is FOSSIL and why does it matter?"))
        first_ms = (time.perf_counter_ns() - start) / 1_000_000
        second = list(kernel.stream_turn(conversation_id="live", question="Why not just use Neo4j?"))
        unsupported = list(kernel.stream_turn(conversation_id="unsupported", question="What is Pujan's favorite food?"))

        if first[-1].type != "turn.complete" or second[-1].type != "turn.complete":
            raise SystemExit("G3 live Slice-1 turns did not complete")
        if event(first, "answer.delta").payload["claimIds"] != ["clm_portfolio_fossil_durable_truth_0001"]:
            raise SystemExit("first Slice-1 answer used unexpected claims")
        if event(second, "answer.planned").payload["dialogueAct"] != "CORRECT_PREMISE":
            raise SystemExit("Neo4j follow-up did not preserve FOSSIL conversation subject")
        if event(second, "turn.accepted").payload["activeSubject"] != "FOSSIL":
            raise SystemExit("follow-up lost active FOSSIL subject")
        if event(second, "answer.delta").payload["claimIds"] != [
            "clm_portfolio_fossil_projection_0001",
            "clm_portfolio_fossil_durable_truth_0001",
        ]:
            raise SystemExit("Neo4j follow-up used unexpected claims")
        if event(unsupported, "answer.delta").payload["text"] != ABSTENTION_TEXT:
            raise SystemExit("unsupported public question did not abstain")
        if event(unsupported, "answer.delta").payload["evidenceIds"]:
            raise SystemExit("unsupported answer unexpectedly carried evidence")

        for events, conversation_id in ((first + second, "live"), (unsupported, "unsupported")):
            validate_events(events, sessions.get(conversation_id))

        supersede_claim(workspace, "clm_portfolio_fossil_durable_truth_0001")
        stale_catalog = FossilClaimCatalog(
            event_store=workspace.event_store,
            source_store=workspace.source_store,
            access=public_runtime_access(),
        )
        stale_kernel = ConversationKernel(
            catalog=stale_catalog,
            retriever=PublicClaimRetriever(stale_catalog, load_retrieval_policy(pack_root / "retrieval-v1.json")),
            sessions=InMemoryConversationSessions(),
            renderer=ClaimBoundTemplateRenderer(),
            verifier=DeterministicGroundingVerifier(),
            clock=SystemClock(),
        )
        stale = list(stale_kernel.stream_turn(conversation_id="stale", question="What is FOSSIL?"))
        if event(stale, "answer.delta").payload["claimIds"]:
            raise SystemExit("superseded claim was presented as current")
        if event(stale, "answer.delta").payload["text"] != ABSTENTION_TEXT:
            raise SystemExit("superseded exact alias did not fail safely to abstention")

        receipt = {
            "status": "PASS",
            "authority": "verification_receipt_only",
            "first_turn_ms": round(first_ms, 4),
            "first_generation": first[0].generation,
            "followup_generation": second[0].generation,
            "active_subject": sessions.get("live").active_subject,
            "first_claim_ids": event(first, "answer.delta").payload["claimIds"],
            "followup_claim_ids": event(second, "answer.delta").payload["claimIds"],
            "unsupported_abstained": True,
            "superseded_claim_not_presented": True,
            "unverified_text_streamed": False,
            "contracts_valid": True,
        }
        rendered = json.dumps(receipt, sort_keys=True)
        print(rendered)
        receipt_path = os.environ.get("G3_RECEIPT_PATH")
        if receipt_path:
            target = Path(receipt_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
