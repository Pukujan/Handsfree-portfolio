from __future__ import annotations

import hashlib
import json
from pathlib import Path

from handsfree_portfolio.adapters.answer_cache import InMemoryAnswerCache
from handsfree_portfolio.adapters.clock import SystemClock
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy
from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions
from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.application.grounded_rendering import ClaimBoundTemplateRenderer, DeterministicGroundingVerifier
from handsfree_portfolio.application.response_cache import ResponseCacheCoordinator
from handsfree_portfolio.application.retrieval import PublicClaimRetriever
from handsfree_portfolio.domain.cache import CachedAnswerArtifact
from handsfree_portfolio.domain.knowledge import PublicClaimRecord

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
POLICY = KNOWLEDGE / "retrieval-v1.json"


class MutableCatalog:
    def __init__(self) -> None:
        payload = json.loads((KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8"))
        self.records = [
            PublicClaimRecord(
                claim_id=claim["claimId"],
                proposition=claim["claimText"],
                evidence_ids=(f"fixture:{claim['claimId']}:evidence",),
                snapshot_ids=(f"fixture:{claim['claimId']}:snapshot",),
                citation_id=f"fixture:{claim['claimId']}:citation",
                source_ref=f"{claim['source']['repository']}@{claim['source']['revision']}:{claim['source']['path']}",
                cited_text=claim["source"]["anchorText"],
            )
            for claim in payload["claims"]
        ]

    def all_supported(self):
        return tuple(self.records)

    def get(self, claim_id: str):
        return next(record for record in self.records if record.claim_id == claim_id)

    def remove(self, claim_id: str) -> None:
        self.records = [record for record in self.records if record.claim_id != claim_id]

    def replace_evidence(self, claim_id: str, evidence_id: str) -> None:
        self.records = [
            PublicClaimRecord(
                claim_id=record.claim_id,
                proposition=record.proposition,
                evidence_ids=(evidence_id,) if record.claim_id == claim_id else record.evidence_ids,
                snapshot_ids=record.snapshot_ids,
                citation_id=record.citation_id,
                source_ref=record.source_ref,
                cited_text=record.cited_text,
            )
            for record in self.records
        ]


class MutableAuthority:
    def __init__(self, value: str = "authority-v1") -> None:
        self.value = value

    def fingerprint(self) -> str:
        return self.value


class CountingRetriever:
    def __init__(self, delegate) -> None:
        self.delegate = delegate
        self.calls = 0

    def retrieve(self, question: str):
        self.calls += 1
        return self.delegate.retrieve(question)


class BrokenCache:
    def __init__(self) -> None:
        self.outages = 0

    def get(self, key: str):
        raise RuntimeError("cache unavailable")

    def put(self, key: str, answer) -> None:
        raise RuntimeError("cache unavailable")

    def delete(self, key: str) -> None:
        raise RuntimeError("cache unavailable")

    def mark_validated_hit(self) -> None:
        raise RuntimeError("cache telemetry unavailable")

    def mark_stale_rejection(self) -> None:
        raise RuntimeError("cache telemetry unavailable")

    def mark_outage(self) -> None:
        self.outages += 1


def policy_revision() -> str:
    return hashlib.sha256(POLICY.read_bytes()).hexdigest()


def make_cached_kernel(*, catalog=None, cache=None, authority=None, sessions=None):
    catalog = catalog or MutableCatalog()
    cache = cache or InMemoryAnswerCache(max_entries=16)
    authority = authority or MutableAuthority()
    verifier = DeterministicGroundingVerifier()
    retriever = CountingRetriever(PublicClaimRetriever(catalog, load_retrieval_policy(POLICY)))
    coordinator = ResponseCacheCoordinator(
        catalog=catalog,
        cache=cache,
        authority=authority,
        verifier=verifier,
        retrieval_policy_revision=policy_revision(),
    )
    kernel = ConversationKernel(
        catalog=catalog,
        retriever=retriever,
        sessions=sessions or InMemoryConversationSessions(),
        renderer=ClaimBoundTemplateRenderer(),
        verifier=verifier,
        clock=SystemClock(),
        response_cache=coordinator,
    )
    return kernel, coordinator, retriever, cache, authority, catalog


def event(events, event_type: str):
    return next(item for item in events if item.type == event_type)


def test_repeated_grounded_question_uses_validated_cache_hit_without_retrieval() -> None:
    kernel, _coordinator, retriever, cache, _authority, _catalog = make_cached_kernel()

    first = list(kernel.stream_turn(conversation_id="same", question="What is FOSSIL?"))
    second = list(kernel.stream_turn(conversation_id="same", question="What is FOSSIL?"))

    assert "retrieval.started" in [item.type for item in first]
    assert "retrieval.started" not in [item.type for item in second]
    assert retriever.calls == 1
    assert event(first, "answer.delta").payload["text"] == event(second, "answer.delta").payload["text"]
    assert event(second, "answer.planned").generation == 2
    assert first[0].turn_id != second[0].turn_id
    metrics = cache.snapshot_metrics()
    assert metrics.hits == 1
    assert metrics.validated_hits == 1
    assert metrics.false_hit_incidents == 0


def test_authority_revision_is_material_cache_key_input() -> None:
    kernel, coordinator, _retriever, _cache, authority, _catalog = make_cached_kernel()
    list(kernel.stream_turn(conversation_id="key-authority", question="What is FOSSIL?"))
    state = kernel.sessions.get("key-authority")
    first_key = coordinator.key_for(question="What is FOSSIL?", subject=state.active_subject, referents=state.referents)
    authority.value = "authority-v2"
    second_key = coordinator.key_for(question="What is FOSSIL?", subject=state.active_subject, referents=state.referents)
    assert first_key != second_key


def test_authority_revision_change_forces_retrieval_miss() -> None:
    kernel, _coordinator, retriever, _cache, authority, _catalog = make_cached_kernel()
    list(kernel.stream_turn(conversation_id="authority", question="What is FOSSIL?"))
    authority.value = "authority-v2"
    second = list(kernel.stream_turn(conversation_id="authority", question="What is FOSSIL?"))
    assert "retrieval.started" in [item.type for item in second]
    assert retriever.calls == 2


def test_current_catalog_revalidation_rejects_stale_cached_claim() -> None:
    kernel, _coordinator, retriever, cache, _authority, catalog = make_cached_kernel()
    list(kernel.stream_turn(conversation_id="stale", question="What is FOSSIL?"))
    catalog.remove("clm_portfolio_fossil_durable_truth_0001")

    second = list(kernel.stream_turn(conversation_id="stale", question="What is FOSSIL?"))
    assert "retrieval.started" in [item.type for item in second]
    assert event(second, "answer.delta").payload["claimIds"] == []
    assert retriever.calls == 2
    assert cache.snapshot_metrics().stale_rejections == 1


def test_current_evidence_drift_rejects_cached_artifact() -> None:
    kernel, _coordinator, retriever, cache, _authority, catalog = make_cached_kernel()
    list(kernel.stream_turn(conversation_id="evidence-drift", question="What is FOSSIL?"))
    catalog.replace_evidence("clm_portfolio_fossil_durable_truth_0001", "fixture:replacement:evidence")

    second = list(kernel.stream_turn(conversation_id="evidence-drift", question="What is FOSSIL?"))
    assert "retrieval.started" in [item.type for item in second]
    assert event(second, "answer.delta").payload["evidenceIds"] == ["fixture:replacement:evidence"]
    assert retriever.calls == 2
    assert cache.snapshot_metrics().stale_rejections == 1


def test_forged_cached_text_is_rejected_by_grounding_verifier() -> None:
    kernel, coordinator, retriever, cache, _authority, _catalog = make_cached_kernel()
    list(kernel.stream_turn(conversation_id="forged", question="What is FOSSIL?"))
    state = kernel.sessions.get("forged")
    key = coordinator.key_for(question="What is FOSSIL?", subject=state.active_subject, referents=state.referents)
    original = cache.get(key)
    assert original is not None
    cache.put(
        key,
        CachedAnswerArtifact(
            text=original.text + " Unsupported expansion.",
            claim_ids=original.claim_ids,
            evidence_ids=original.evidence_ids,
        ),
    )

    second = list(kernel.stream_turn(conversation_id="forged", question="What is FOSSIL?"))
    assert "retrieval.started" in [item.type for item in second]
    assert "Unsupported expansion." not in event(second, "answer.delta").payload["text"]
    assert retriever.calls == 2
    assert cache.snapshot_metrics().stale_rejections == 1


def test_cache_outage_degrades_to_normal_retrieval() -> None:
    cache = BrokenCache()
    kernel, _coordinator, retriever, _cache, _authority, _catalog = make_cached_kernel(cache=cache)
    events = list(kernel.stream_turn(conversation_id="outage", question="What is FOSSIL?"))
    assert events[-1].type == "turn.complete"
    assert "retrieval.started" in [item.type for item in events]
    assert retriever.calls == 1
    assert cache.outages >= 1


def test_shared_cache_key_contains_no_raw_question_text() -> None:
    kernel, _coordinator, _retriever, cache, _authority, _catalog = make_cached_kernel()
    list(kernel.stream_turn(conversation_id="privacy", question="What is FOSSIL?"))
    assert len(cache.keys()) == 1
    key = cache.keys()[0]
    assert len(key) == 64
    assert "fossil" not in key.lower()
    int(key, 16)


def test_material_conversation_context_prevents_cross_context_hit() -> None:
    kernel, _coordinator, retriever, _cache, _authority, _catalog = make_cached_kernel()
    list(kernel.stream_turn(conversation_id="with-context", question="What is FOSSIL?"))
    contextual = list(kernel.stream_turn(conversation_id="with-context", question="Why not just use Neo4j?"))
    fresh = list(kernel.stream_turn(conversation_id="fresh", question="Why not just use Neo4j?"))

    assert event(contextual, "answer.delta").payload["text"].startswith("Not quite. ")
    assert not event(fresh, "answer.delta").payload["text"].startswith("Not quite. ")
    assert "retrieval.started" in [item.type for item in fresh]
    assert retriever.calls == 3


def test_abstentions_are_not_cached_as_shared_conclusions() -> None:
    kernel, _coordinator, retriever, cache, _authority, _catalog = make_cached_kernel()
    first = list(kernel.stream_turn(conversation_id="unsupported", question="What is Pujan's favorite food?"))
    second = list(kernel.stream_turn(conversation_id="unsupported", question="What is Pujan's favorite food?"))
    assert event(first, "answer.delta").payload["claimIds"] == []
    assert event(second, "answer.delta").payload["claimIds"] == []
    assert "retrieval.started" in [item.type for item in second]
    assert retriever.calls == 2
    assert len(cache) == 0
