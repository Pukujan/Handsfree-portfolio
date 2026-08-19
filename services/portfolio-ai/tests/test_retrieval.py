from __future__ import annotations

import json
from pathlib import Path

from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy, should_graph_drilldown
from handsfree_portfolio.application.retrieval import PublicClaimRetriever
from handsfree_portfolio.domain.knowledge import PublicClaimRecord

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
BENCHMARK = ROOT / "benchmarks" / "retrieval" / "slice1-v1.json"
POLICY = KNOWLEDGE / "retrieval-v1.json"


class FixtureCatalog:
    def __init__(self) -> None:
        payload = json.loads((KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8"))
        self.records = tuple(
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
        )

    def all_supported(self):
        return self.records

    def get(self, claim_id: str):
        return next(record for record in self.records if record.claim_id == claim_id)


def test_slice1_retrieval_benchmark_cases() -> None:
    retriever = PublicClaimRetriever(FixtureCatalog(), load_retrieval_policy(POLICY))
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))["cases"]

    for case in cases:
        result = retriever.retrieve(case["question"])
        expected = tuple(case["expectedClaimIds"])
        if case["expectAbstain"]:
            assert result.abstained, case["id"]
            continue

        assert not result.abstained, case["id"]
        assert set(expected).issubset(result.claim_ids), (case["id"], result)
        assert result.claim_ids[0] == expected[0], (case["id"], result)


def test_graph_drilldown_is_triggered_only_for_evidence_intent() -> None:
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        expected = bool(case.get("expectGraphDrilldown", False))
        assert should_graph_drilldown(POLICY, case["question"]) is expected, case["id"]


def test_exact_aliases_do_not_resolve_unknown_claim_ids() -> None:
    policy = load_retrieval_policy(POLICY)
    policy = type(policy)(
        exact_aliases={**policy.exact_aliases, "poisoned alias": ("clm_not_in_authorized_catalog",)},
        concepts=policy.concepts,
        top_k=policy.top_k,
        minimum_sparse_score=policy.minimum_sparse_score,
    )
    result = PublicClaimRetriever(FixtureCatalog(), policy).retrieve("poisoned alias")
    assert result.abstained
