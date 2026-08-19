from __future__ import annotations

import json
import os
import shutil
import statistics
import tempfile
import time
from pathlib import Path

from handsfree_portfolio.adapters.fossil_claim_catalog import FossilClaimCatalog
from handsfree_portfolio.adapters.fossil_pack import FossilPackWorkspace, FossilSchemaRoot, ingest_supported_claim, public_runtime_access
from handsfree_portfolio.adapters.neo4j_projection import Neo4jClaimProjectionAdapter
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy, should_graph_drilldown
from handsfree_portfolio.application.retrieval import PublicClaimRetriever

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
BENCHMARK = ROOT / "benchmarks" / "retrieval" / "slice1-v1.json"
POLICY = KNOWLEDGE / "retrieval-v1.json"
OBSERVED_AT = "2026-08-19T20:30:00Z"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[index]


def connect_projection() -> Neo4jClaimProjectionAdapter:
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
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

    claim_document = json.loads((KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8"))
    cases = json.loads(BENCHMARK.read_text(encoding="utf-8"))["cases"]

    with tempfile.TemporaryDirectory(prefix="handsfree-g2-") as directory:
        pack_root = Path(directory) / "portfolio-public"
        pack_root.mkdir()
        shutil.copy(KNOWLEDGE / "manifest.json", pack_root / "manifest.json")
        shutil.copy(KNOWLEDGE / "source-policy.json", pack_root / "source-policy.json")
        workspace = FossilPackWorkspace(pack_root, FossilSchemaRoot(Path(schema_root)))

        for claim in claim_document["claims"]:
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
        retriever = PublicClaimRetriever(catalog, load_retrieval_policy(POLICY))

        projection = connect_projection()
        try:
            receipts = projection.rebuild(events_root=workspace.event_store.root)
            if any(receipt.status != "applied" for receipt in receipts):
                raise SystemExit(f"G2 projection rebuild failed: {receipts}")

            top1_correct = 0
            supported_cases = 0
            recall_sum = 0.0
            precision_sum = 0.0
            abstain_correct = 0
            abstain_cases = 0
            lane_counts: dict[str, int] = {}
            retrieval_latencies_ms: list[float] = []
            graph_latencies_ms: list[float] = []
            graph_integrity_checks = 0
            graph_integrity_pass = 0
            graph_incremental_claims: set[str] = set()
            case_receipts = []

            for case in cases:
                samples: list[float] = []
                result = None
                for _ in range(25):
                    start = time.perf_counter_ns()
                    result = retriever.retrieve(case["question"])
                    samples.append((time.perf_counter_ns() - start) / 1_000_000)
                assert result is not None
                retrieval_latencies_ms.extend(samples)
                lane_counts[result.lane] = lane_counts.get(result.lane, 0) + 1

                expected = tuple(case["expectedClaimIds"])
                expected_set = set(expected)
                result_set = set(result.claim_ids)
                if case["expectAbstain"]:
                    abstain_cases += 1
                    abstain_correct += int(result.abstained)
                else:
                    supported_cases += 1
                    top1_correct += int(bool(result.claim_ids) and result.claim_ids[0] == expected[0])
                    recall_sum += len(expected_set & result_set) / len(expected_set)
                    precision_sum += len(expected_set & result_set) / max(1, len(result_set))

                graph_paths = ()
                if should_graph_drilldown(POLICY, case["question"]) and result.claim_ids:
                    graph_samples: list[float] = []
                    for _ in range(10):
                        start = time.perf_counter_ns()
                        graph_paths = projection.evidence_paths(result.claim_ids)
                        graph_samples.append((time.perf_counter_ns() - start) / 1_000_000)
                    graph_latencies_ms.extend(graph_samples)
                    by_claim = {path.claim_id: path for path in graph_paths}
                    for claim_id in result.claim_ids:
                        graph_integrity_checks += 1
                        record = catalog.get(claim_id)
                        path = by_claim.get(claim_id)
                        if path and path.evidence_ids == tuple(sorted(record.evidence_ids)) and path.snapshot_ids == tuple(sorted(record.snapshot_ids)):
                            graph_integrity_pass += 1
                    graph_incremental_claims.update(set(by_claim) - result_set)

                case_receipts.append(
                    {
                        "id": case["id"],
                        "lane": result.lane,
                        "expected": list(expected),
                        "returned": list(result.claim_ids),
                        "abstained": result.abstained,
                        "graph_drilldown": bool(graph_paths),
                    }
                )

            top1_accuracy = top1_correct / supported_cases
            recall_at_2 = recall_sum / supported_cases
            precision_at_2 = precision_sum / supported_cases
            abstention_accuracy = abstain_correct / abstain_cases
            graph_evidence_integrity = graph_integrity_pass / max(1, graph_integrity_checks)

            if top1_accuracy < 1.0 or recall_at_2 < 1.0 or abstention_accuracy < 1.0:
                raise SystemExit(
                    json.dumps(
                        {
                            "status": "FAIL_BASELINE",
                            "top1_accuracy": top1_accuracy,
                            "recall_at_2": recall_at_2,
                            "abstention_accuracy": abstention_accuracy,
                            "cases": case_receipts,
                        },
                        sort_keys=True,
                    )
                )
            if graph_evidence_integrity < 1.0:
                raise SystemExit("graph evidence paths did not match authoritative FOSSIL catalog")

            receipt = {
                "status": "PASS",
                "policy_id": "slice1-retrieval-v1",
                "case_count": len(cases),
                "top1_accuracy": round(top1_accuracy, 4),
                "recall_at_2": round(recall_at_2, 4),
                "precision_at_2": round(precision_at_2, 4),
                "abstention_accuracy": round(abstention_accuracy, 4),
                "lane_counts": lane_counts,
                "retrieval_latency_ms": {
                    "median": round(statistics.median(retrieval_latencies_ms), 4),
                    "p95": round(percentile(retrieval_latencies_ms, 0.95), 4),
                },
                "graph_evidence_integrity": round(graph_evidence_integrity, 4),
                "graph_latency_ms": {
                    "median": round(statistics.median(graph_latencies_ms), 4) if graph_latencies_ms else 0.0,
                    "p95": round(percentile(graph_latencies_ms, 0.95), 4) if graph_latencies_ms else 0.0,
                },
                "graph_incremental_claim_count": len(graph_incremental_claims),
                "decision": {
                    "embedding_model_required_for_slice1": False,
                    "graph_default_hot_path": False,
                    "graph_evidence_drilldown": True,
                    "graphiti_required_for_slice1": False,
                },
                "cases": case_receipts,
            }
            print(json.dumps(receipt, sort_keys=True))
        finally:
            projection.close()


if __name__ == "__main__":
    main()
