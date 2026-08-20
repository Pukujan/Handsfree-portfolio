from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_RECEIPT = ROOT / "assurance" / "receipts" / "G6-SEMANTIC-TRANSFER-v1.json"
SEMANTIC_CONTRACT = ROOT / "assurance" / "conversation" / "semantic-evaluation-v1.json"
EXPECTED_SEMANTIC_EVIDENCE_REVISION = "d1e543d92748e563258c314c90d4d46bb638dc03"
EXPECTED_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EXPECTED_PACKAGE_VERSION = "5.6.1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_semantic_rejection() -> dict:
    receipt = load(SEMANTIC_RECEIPT)
    contract = load(SEMANTIC_CONTRACT)
    if receipt.get("status") != "PASS" or receipt.get("decision") != "SEMANTIC_BRIDGE_NOT_EARNED":
        raise SystemExit("semantic transfer evidence must remain an explicit rejected experiment")
    evidence = receipt.get("evidenceRun", {})
    if evidence.get("candidateRevision") != EXPECTED_SEMANTIC_EVIDENCE_REVISION:
        raise SystemExit("semantic rejection receipt revision drift")
    experiment = receipt.get("experiment", {})
    implementation = contract.get("implementation", {})
    if experiment.get("modelRevision") != EXPECTED_MODEL_REVISION:
        raise SystemExit("semantic rejection model revision drift")
    if experiment.get("packageVersion") != EXPECTED_PACKAGE_VERSION:
        raise SystemExit("semantic rejection package version drift")
    if implementation.get("modelRevision") != experiment.get("modelRevision"):
        raise SystemExit("semantic evaluation contract and receipt model revision differ")
    if implementation.get("packageVersion") != experiment.get("packageVersion"):
        raise SystemExit("semantic evaluation contract and receipt package version differ")
    if any(receipt.get("authority", {}).values()):
        raise SystemExit("rejected semantic experiment cannot gain authority")
    policy = receipt.get("selectionPolicy", {})
    results = receipt.get("results", {})
    if results.get("semanticMrdaUserActTop1Accuracy", 1.0) >= policy.get("minimumMrdaUserActTop1Accuracy", 0.0):
        raise SystemExit("semantic rejection receipt no longer supports rejection on MRDA accuracy")
    if results.get("mrdaAbsoluteImprovementOverLexical", 1.0) >= policy.get("minimumMrdaAbsoluteImprovementOverLexical", 0.0):
        raise SystemExit("semantic rejection receipt no longer supports rejection on transfer improvement")
    return receipt


def validate_shared_ontology_receipt(path: Path) -> dict:
    receipt = load(path)
    if receipt.get("status") != "PASS":
        raise SystemExit("shared ontology experiment did not complete")
    if receipt.get("sourceRevisions", {}).get("multiwoz") != "fe0c8e65cfcd8462bd33c86e35f21addc84ca82b":
        raise SystemExit("shared ontology MultiWOZ revision drift")
    if receipt.get("sourceRevisions", {}).get("mrda") != "58006b32d4e36ca518e365899924cd56035466a2":
        raise SystemExit("shared ontology MRDA revision drift")
    if receipt.get("rawDialogueEmitted") is not False or receipt.get("factualAuthority") is not False:
        raise SystemExit("shared ontology experiment crossed the style-only authority boundary")
    policy = receipt.get("selectionPolicy", {})
    if policy != {
        "minimumGraphCoverage": 0.9,
        "minimumMrdaBalancedAccuracy": 0.75,
        "minimumMrdaQueryRecall": 0.65,
        "minimumMultiwozBalancedAccuracy": 0.75,
        "minimumRelativeNllImprovement": 0.02,
    }:
        raise SystemExit("shared ontology predeclared selection policy drift")
    return receipt


def main() -> None:
    machine_path_value = os.environ.get("G6_MACHINE_RECEIPT_PATH")
    ontology_path_value = os.environ.get("G6_SHARED_ONTOLOGY_RECEIPT_PATH")
    if not machine_path_value or not ontology_path_value:
        raise SystemExit("G6_MACHINE_RECEIPT_PATH and G6_SHARED_ONTOLOGY_RECEIPT_PATH are required")
    machine_path = Path(machine_path_value)
    ontology_path = Path(ontology_path_value)
    if not machine_path.exists() or not ontology_path.exists():
        raise SystemExit("machine or shared ontology receipt is missing")

    machine = load(machine_path)
    semantic = validate_semantic_rejection()
    ontology = validate_shared_ontology_receipt(ontology_path)

    semantic_results = semantic["results"]
    machine["semanticMatcherEvidence"] = "SEMANTIC_BRIDGE_TESTED_AND_REJECTED"
    machine["semanticTransferSummary"] = {
        "decision": semantic["decision"],
        "evidenceRevision": semantic["evidenceRun"]["candidateRevision"],
        "workflowRunId": semantic["evidenceRun"]["workflowRunId"],
        "modelId": semantic["experiment"]["modelId"],
        "modelRevision": semantic["experiment"]["modelRevision"],
        "packageVersion": semantic["experiment"]["packageVersion"],
        "multiwozUserActTop1Accuracy": semantic_results["multiwozUserActTop1Accuracy"],
        "lexicalMrdaUserActTop1Accuracy": semantic_results["lexicalMrdaUserActTop1Accuracy"],
        "semanticMrdaUserActTop1Accuracy": semantic_results["semanticMrdaUserActTop1Accuracy"],
        "mrdaAbsoluteImprovementOverLexical": semantic_results["mrdaAbsoluteImprovementOverLexical"],
        "factualAuthority": False,
        "runtimeAdmitted": False,
    }
    machine["sharedOntologySummary"] = {
        "selectedClassifier": ontology["selectedClassifier"],
        "ontologyBridgeEvidence": ontology["ontologyBridgeEvidence"],
        "distributionalGraphEvidence": ontology["distributionalGraphEvidence"],
        "runtimeGraphEvidence": ontology["runtimeGraphEvidence"],
        "oracleFullMoveDistributionGraph": ontology["oracleFullMoveDistributionGraph"],
        "binaryOracleDistributionGraph": ontology["binaryOracleDistributionGraph"],
        "selectedClassifierDistributionGraph": ontology["selectedClassifierDistributionGraph"],
        "classifierCandidates": ontology["classifierCandidates"],
        "factualAuthority": False,
    }
    machine["nextNaturalnessDecision"] = {
        "embeddingBridge": "REJECTED",
        "sharedOntologyBridge": ontology["ontologyBridgeEvidence"],
        "distributionalDiscourseGraph": ontology["distributionalGraphEvidence"],
        "runtimeGraph": ontology["runtimeGraphEvidence"],
    }

    machine_path.write_text(json.dumps(machine, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(machine, sort_keys=True))


if __name__ == "__main__":
    main()
