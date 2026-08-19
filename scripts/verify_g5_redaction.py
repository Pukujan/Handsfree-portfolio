from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from handsfree_portfolio.adapters.answer_cache import InMemoryAnswerCache
from handsfree_portfolio.adapters.cache_authority import FossilPackAuthorityFingerprint
from handsfree_portfolio.adapters.clock import SystemClock
from handsfree_portfolio.adapters.fossil_claim_catalog import FossilClaimCatalog
from handsfree_portfolio.adapters.fossil_pack import FossilPackWorkspace, FossilSchemaRoot, ingest_supported_claim, public_runtime_access
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy
from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions
from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.application.grounded_rendering import ABSTENTION_TEXT, ClaimBoundTemplateRenderer, DeterministicGroundingVerifier
from handsfree_portfolio.application.response_cache import ResponseCacheCoordinator
from handsfree_portfolio.application.retrieval import PublicClaimRetriever

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
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


def main() -> None:
    schema_root = os.environ.get("FOSSIL_SCHEMA_ROOT")
    if not schema_root:
        raise SystemExit("FOSSIL_SCHEMA_ROOT is required")
    claims = json.loads((KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8"))["claims"]

    with tempfile.TemporaryDirectory(prefix="handsfree-g5-redaction-") as directory:
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
                observed_at="2026-08-19T21:35:00Z",
            )

        access = public_runtime_access()
        catalog = FossilClaimCatalog(event_store=workspace.event_store, source_store=workspace.source_store, access=access)
        policy_path = pack_root / "retrieval-v1.json"
        retriever = CountingRetriever(PublicClaimRetriever(catalog, load_retrieval_policy(policy_path)))
        verifier = DeterministicGroundingVerifier()
        cache = InMemoryAnswerCache(max_entries=8)
        authority = FossilPackAuthorityFingerprint(event_store=workspace.event_store, access=access)
        coordinator = ResponseCacheCoordinator(
            catalog=catalog,
            cache=cache,
            authority=authority,
            verifier=verifier,
            retrieval_policy_revision=hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        )
        kernel = ConversationKernel(
            catalog=catalog,
            retriever=retriever,
            sessions=InMemoryConversationSessions(),
            renderer=ClaimBoundTemplateRenderer(),
            verifier=verifier,
            clock=SystemClock(),
            response_cache=coordinator,
        )

        first = list(kernel.stream_turn(conversation_id="redaction", question=QUESTION))
        hit = list(kernel.stream_turn(conversation_id="redaction", question=QUESTION))
        if event(first, "answer.delta").payload["claimIds"] != [CLAIM_ID]:
            raise SystemExit("failed to seed supported claim before redaction")
        if "retrieval.started" in [item.type for item in hit]:
            raise SystemExit("failed to establish pre-redaction validated cache hit")

        before = authority.fingerprint()
        supported_event = next(
            item
            for item in workspace.event_store.iter_events()
            if item["event_type"] == "claim.state_changed" and item["subject_refs"] == [CLAIM_ID]
        )
        workspace.event_store.redact(
            supported_event["event_id"],
            reason="G5 redaction invalidation verification",
            authority="handsfree-g5-verifier",
            redacted_at="2026-08-19T21:36:00Z",
            request_ref="g5-redaction-proof-001",
        )
        after = authority.fingerprint()
        if before == after:
            raise SystemExit("event redaction did not alter cache authority fingerprint")

        post_redaction = list(kernel.stream_turn(conversation_id="redaction", question=QUESTION))
        if "retrieval.started" not in [item.type for item in post_redaction]:
            raise SystemExit("redaction did not invalidate the previous cache namespace")
        if event(post_redaction, "answer.delta").payload["claimIds"]:
            raise SystemExit("redacted support event still allowed cached/current claim publication")
        if event(post_redaction, "answer.delta").payload["text"] != ABSTENTION_TEXT:
            raise SystemExit("redacted claim did not fail safely to abstention")
        if retriever.calls != 2:
            raise SystemExit(f"expected two retrieval calls across miss/hit/redaction sequence, got {retriever.calls}")

        receipt = {
            "status": "PASS",
            "authority": "verification_receipt_only",
            "pre_redaction_validated_hit": True,
            "authority_revision_changed_after_redaction": True,
            "redacted_support_not_served": True,
            "post_redaction_forced_retrieval": True,
            "retrieval_calls_across_miss_hit_redaction": retriever.calls,
            "redaction_tombstone_present": workspace.event_store.get_redaction(supported_event["event_id"]) is not None,
            "false_hit_incidents": 0,
        }
        rendered = json.dumps(receipt, sort_keys=True)
        print(rendered)
        target_value = os.environ.get("G5_REDACTION_RECEIPT_PATH")
        if target_value:
            target = Path(target_value)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
