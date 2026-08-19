from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from handsfree_portfolio.adapters.answer_cache import InMemoryAnswerCache
from handsfree_portfolio.adapters.cache_authority import FossilPackAuthorityFingerprint
from handsfree_portfolio.adapters.clock import SystemClock
from handsfree_portfolio.adapters.fossil_claim_catalog import FossilClaimCatalog
from handsfree_portfolio.adapters.fossil_pack import (
    FossilPackWorkspace,
    FossilSchemaRoot,
    PUBLIC_PACK_ID,
    ingest_supported_claim,
    public_runtime_access,
)
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy
from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions
from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.application.grounded_rendering import (
    ABSTENTION_TEXT,
    ClaimBoundTemplateRenderer,
    DeterministicGroundingVerifier,
)
from handsfree_portfolio.application.response_cache import ResponseCacheCoordinator
from handsfree_portfolio.application.retrieval import PublicClaimRetriever
from handsfree_portfolio.domain.cache import CachedAnswerArtifact

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
OBSERVED_AT = "2026-08-19T21:30:00Z"
QUESTION = "What is FOSSIL?"
CLAIM_ID = "clm_portfolio_fossil_durable_truth_0001"


class CountingRetriever:
    def __init__(self, delegate) -> None:
        self.delegate = delegate
        self.calls = 0

    def retrieve(self, question: str):
        self.calls += 1
        return self.delegate.retrieve(question)


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
            "occurred_at": "2026-08-19T21:31:00Z",
            "recorded_at": "2026-08-19T21:31:00.000000Z",
            "pack_id": PUBLIC_PACK_ID,
            "actor": {"actor_type": "system", "actor_id": "handsfree-g5-live-verifier"},
            "subject_refs": [claim_id],
            "correlation_id": f"g5-supersede:{claim_id}",
            "caused_by_event_ids": [prior["event_id"]],
            "evidence_refs": list(prior["evidence_refs"]),
            "source_snapshot_refs": list(prior["source_snapshot_refs"]),
            "idempotency_key": f"g5-supersede:{claim_id}:v1",
            "payload": {
                "from_state": "supported",
                "to_state": "superseded",
                "reason": "G5 lifecycle invalidation verification fixture",
                "citation": prior["payload"]["citation"],
            },
            "provenance": {
                "method": "g5_live_cache_invalidation_verification",
                "prompt_or_policy_ref": "docs/DEVELOPMENT-METHOD.md",
                "benchmark_ref": "g5-live-v1",
            },
        }
    )


def timed_turn(kernel: ConversationKernel, *, conversation_id: str, question: str):
    start = time.perf_counter_ns()
    events = list(kernel.stream_turn(conversation_id=conversation_id, question=question))
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    return events, elapsed_ms


def main() -> None:
    schema_root = os.environ.get("FOSSIL_SCHEMA_ROOT")
    if not schema_root:
        raise SystemExit("FOSSIL_SCHEMA_ROOT is required")

    claims = json.loads((KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8"))["claims"]

    with tempfile.TemporaryDirectory(prefix="handsfree-g5-") as directory:
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

        access = public_runtime_access()
        catalog = FossilClaimCatalog(
            event_store=workspace.event_store,
            source_store=workspace.source_store,
            access=access,
        )
        policy_path = pack_root / "retrieval-v1.json"
        retriever = CountingRetriever(PublicClaimRetriever(catalog, load_retrieval_policy(policy_path)))
        cache = InMemoryAnswerCache(max_entries=16)
        verifier = DeterministicGroundingVerifier()
        authority = FossilPackAuthorityFingerprint(event_store=workspace.event_store, access=access)
        coordinator = ResponseCacheCoordinator(
            catalog=catalog,
            cache=cache,
            authority=authority,
            verifier=verifier,
            retrieval_policy_revision=hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        )
        sessions = InMemoryConversationSessions()
        kernel = ConversationKernel(
            catalog=catalog,
            retriever=retriever,
            sessions=sessions,
            renderer=ClaimBoundTemplateRenderer(),
            verifier=verifier,
            clock=SystemClock(),
            response_cache=coordinator,
        )

        authority_before = authority.fingerprint()
        first, first_ms = timed_turn(kernel, conversation_id="live", question=QUESTION)
        second, second_ms = timed_turn(kernel, conversation_id="live", question=QUESTION)

        if first[-1].type != "turn.complete" or second[-1].type != "turn.complete":
            raise SystemExit("G5 repeated grounded turns did not complete")
        if "retrieval.started" not in [item.type for item in first]:
            raise SystemExit("first turn unexpectedly bypassed retrieval")
        if "retrieval.started" in [item.type for item in second]:
            raise SystemExit("validated cache hit did not skip retrieval")
        if retriever.calls != 1:
            raise SystemExit(f"expected one retrieval after validated hit, got {retriever.calls}")
        if event(first, "answer.delta").payload["claimIds"] != [CLAIM_ID]:
            raise SystemExit("first turn used unexpected claim set")
        if event(second, "answer.delta").payload["claimIds"] != [CLAIM_ID]:
            raise SystemExit("cache hit used unexpected claim set")
        if event(first, "answer.delta").payload["evidenceIds"] != event(second, "answer.delta").payload["evidenceIds"]:
            raise SystemExit("validated hit drifted from current evidence")
        if first[0].turn_id == second[0].turn_id or first[0].generation == second[0].generation:
            raise SystemExit("cache replay reused stale turn identity")

        # A durable lifecycle transition changes the authority revision, making the old key ineligible.
        supersede_claim(workspace, CLAIM_ID)
        authority_after = authority.fingerprint()
        if authority_after == authority_before:
            raise SystemExit("durable lifecycle change did not alter cache authority fingerprint")
        third, third_ms = timed_turn(kernel, conversation_id="live", question=QUESTION)
        if "retrieval.started" not in [item.type for item in third]:
            raise SystemExit("authority change did not force normal retrieval")
        if event(third, "answer.delta").payload["claimIds"]:
            raise SystemExit("superseded claim was served after cache authority changed")
        if event(third, "answer.delta").payload["text"] != ABSTENTION_TEXT:
            raise SystemExit("superseded claim did not fail safely to abstention")
        if retriever.calls != 2:
            raise SystemExit("post-lifecycle turn did not execute exactly one additional retrieval")

        # Rebuild a supported pack in a separate workspace and prove a forged cache artifact fails closed.
        forged_root = Path(directory) / "forged-public"
        forged_root.mkdir()
        for filename in ("manifest.json", "source-policy.json", "retrieval-v1.json"):
            shutil.copy(KNOWLEDGE / filename, forged_root / filename)
        forged_workspace = FossilPackWorkspace(forged_root, FossilSchemaRoot(Path(schema_root)))
        for claim in claims:
            ingest_supported_claim(
                forged_workspace,
                policy_path=forged_root / "source-policy.json",
                claim=claim,
                observed_at="2026-08-19T21:32:00Z",
            )
        forged_access = public_runtime_access()
        forged_catalog = FossilClaimCatalog(
            event_store=forged_workspace.event_store,
            source_store=forged_workspace.source_store,
            access=forged_access,
        )
        forged_retriever = CountingRetriever(PublicClaimRetriever(forged_catalog, load_retrieval_policy(forged_root / "retrieval-v1.json")))
        forged_cache = InMemoryAnswerCache(max_entries=8)
        forged_authority = FossilPackAuthorityFingerprint(event_store=forged_workspace.event_store, access=forged_access)
        forged_coordinator = ResponseCacheCoordinator(
            catalog=forged_catalog,
            cache=forged_cache,
            authority=forged_authority,
            verifier=verifier,
            retrieval_policy_revision=hashlib.sha256((forged_root / "retrieval-v1.json").read_bytes()).hexdigest(),
        )
        forged_sessions = InMemoryConversationSessions()
        forged_kernel = ConversationKernel(
            catalog=forged_catalog,
            retriever=forged_retriever,
            sessions=forged_sessions,
            renderer=ClaimBoundTemplateRenderer(),
            verifier=verifier,
            clock=SystemClock(),
            response_cache=forged_coordinator,
        )
        seeded = list(forged_kernel.stream_turn(conversation_id="forged", question=QUESTION))
        seeded_state = forged_sessions.get("forged")
        forged_key = forged_coordinator.key_for(
            question=QUESTION,
            subject=seeded_state.active_subject,
            referents=seeded_state.referents,
        )
        current_artifact = forged_cache.get(forged_key)
        if current_artifact is None:
            raise SystemExit("failed to seed forged-artifact verification cache")
        forged_cache.put(
            forged_key,
            CachedAnswerArtifact(
                text=current_artifact.text + " Unsupported forged expansion.",
                claim_ids=current_artifact.claim_ids,
                evidence_ids=current_artifact.evidence_ids,
            ),
        )
        forged = list(forged_kernel.stream_turn(conversation_id="forged", question=QUESTION))
        if "retrieval.started" not in [item.type for item in forged]:
            raise SystemExit("forged cache artifact was not rejected before fallback retrieval")
        if "Unsupported forged expansion." in event(forged, "answer.delta").payload["text"]:
            raise SystemExit("forged cached language reached publication")
        if forged_cache.snapshot_metrics().stale_rejections < 1:
            raise SystemExit("forged cache rejection was not observable")

        metrics = cache.snapshot_metrics()
        receipt = {
            "status": "PASS",
            "authority": "verification_receipt_only",
            "first_turn_ms": round(first_ms, 4),
            "validated_hit_turn_ms": round(second_ms, 4),
            "post_lifecycle_turn_ms": round(third_ms, 4),
            "observed_latency_saved_ms": round(first_ms - second_ms, 4),
            "retrieval_calls_after_two_equal_questions": 1,
            "validated_hit_skipped_retrieval": True,
            "fresh_turn_identity_on_hit": True,
            "authority_revision_changed_after_lifecycle_event": True,
            "superseded_claim_not_served": True,
            "forged_cached_text_rejected": True,
            "cache_hit_count": metrics.hits,
            "validated_hit_count": metrics.validated_hits,
            "stale_rejection_count": metrics.stale_rejections,
            "cache_outages": metrics.outages,
            "false_hit_incidents": metrics.false_hit_incidents,
            "model_tokens_saved": 0,
            "latency_gate_note": "Latency is observational in CI; G5 admission depends on authority/correctness plus measured practical benefit, not a brittle single-run threshold.",
        }
        rendered = json.dumps(receipt, sort_keys=True)
        print(rendered)
        receipt_path = os.environ.get("G5_RECEIPT_PATH")
        if receipt_path:
            target = Path(receipt_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
