from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.finalize_g6_naturalness_receipt import (
    finalize_receipt,
    validate_semantic_rejection,
    validate_shared_ontology_receipt,
    validate_surface_envelope_receipt,
)


def test_frozen_semantic_rejection_is_non_authoritative_and_below_admission_thresholds() -> None:
    receipt = validate_semantic_rejection()
    assert receipt["decision"] == "SEMANTIC_BRIDGE_NOT_EARNED"
    assert receipt["results"]["semanticMrdaUserActTop1Accuracy"] < receipt["selectionPolicy"]["minimumMrdaUserActTop1Accuracy"]
    assert receipt["results"]["mrdaAbsoluteImprovementOverLexical"] < receipt["selectionPolicy"]["minimumMrdaAbsoluteImprovementOverLexical"]
    assert not any(receipt["authority"].values())


def shared_ontology_receipt(**overrides: object) -> dict:
    payload = {
        "status": "PASS",
        "sourceRevisions": {
            "multiwoz": "fe0c8e65cfcd8462bd33c86e35f21addc84ca82b",
            "mrda": "58006b32d4e36ca518e365899924cd56035466a2",
        },
        "rawDialogueEmitted": False,
        "factualAuthority": False,
        "selectionPolicy": {
            "minimumGraphCoverage": 0.9,
            "minimumMrdaBalancedAccuracy": 0.75,
            "minimumMrdaQueryRecall": 0.65,
            "minimumMultiwozBalancedAccuracy": 0.75,
            "minimumRelativeNllImprovement": 0.02,
        },
        "selectedClassifier": None,
        "ontologyBridgeEvidence": "SHARED_ONTOLOGY_BRIDGE_NOT_EARNED",
        "distributionalGraphEvidence": "DISTRIBUTIONAL_DISCOURSE_GRAPH_NOT_EARNED",
        "runtimeGraphEvidence": "BINARY_RUNTIME_GRAPH_NOT_EARNED",
        "oracleFullMoveDistributionGraph": {"relativeNllImprovement": 0.00959},
        "binaryOracleDistributionGraph": {"relativeNllImprovement": 0.00316},
        "selectedClassifierDistributionGraph": None,
        "classifierCandidates": [],
    }
    payload.update(overrides)
    return payload


def surface_receipt(**overrides: object) -> dict:
    payload = {
        "status": "PASS",
        "qualificationStatus": "PASS",
        "metricRevision": "short_question_floor_v2",
        "sourceRevisions": {
            "multiwoz": "fe0c8e65cfcd8462bd33c86e35f21addc84ca82b",
            "mrda": "58006b32d4e36ca518e365899924cd56035466a2",
        },
        "humanReference": {
            "multiwozRequestInform": {"ratioQuestionFloorWords": 5},
            "mrdaQuestionStatement": {"ratioQuestionFloorWords": 5},
        },
        "productionSurface": {
            "pairCount": 46,
            "medianResponseWords": 11,
            "p90ResponseWords": 11,
            "p95ResponseWords": 11,
            "p90ResponseToQuestionWordRatio": 2.75,
            "ratioQuestionFloorWords": 5,
            "p90FloorNormalizedResponseToQuestionWordRatio": 2.2,
            "assistantesePrefixRate": 0.0,
            "unsolicitedClosingRate": 0.0,
            "headingOrListRate": 0.0,
            "misappliedCorrectionRate": 0.0,
        },
        "surfaceEnvelope": {
            "ratioQuestionFloorWords": 5,
            "maximumMedianResponseWords": 29.0,
            "maximumP90FloorNormalizedResponseToQuestionWordRatio": 2.5454545454545454,
            "rawP90ResponseToQuestionWordRatioDiagnosticOnly": True,
        },
        "measuredDefects": [],
        "rawDialogueEmitted": False,
        "factualAuthority": False,
        "rendererModified": False,
        "planningModified": True,
    }
    payload.update(overrides)
    return payload


def write_receipt(tmp_path: Path, payload: dict, name: str = "receipt.json") -> Path:
    target = tmp_path / name
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_shared_ontology_finalizer_rejects_authority_drift(tmp_path: Path) -> None:
    target = write_receipt(tmp_path, shared_ontology_receipt(factualAuthority=True))
    with pytest.raises(SystemExit, match="style-only authority boundary"):
        validate_shared_ontology_receipt(target)


def test_shared_ontology_finalizer_rejects_threshold_drift(tmp_path: Path) -> None:
    payload = shared_ontology_receipt()
    payload["selectionPolicy"]["minimumMrdaBalancedAccuracy"] = 0.70
    target = write_receipt(tmp_path, payload)
    with pytest.raises(SystemExit, match="selection policy drift"):
        validate_shared_ontology_receipt(target)


def test_surface_pass_receipt_validates(tmp_path: Path) -> None:
    target = write_receipt(tmp_path, surface_receipt())
    validated = validate_surface_envelope_receipt(target)
    assert validated["qualificationStatus"] == "PASS"
    assert validated["measuredDefects"] == []


def test_surface_nonpass_cannot_promote_gate(tmp_path: Path) -> None:
    target = write_receipt(tmp_path, surface_receipt(qualificationStatus="MEASURED_SURFACE_DEFECT"))
    with pytest.raises(SystemExit, match="has not qualified"):
        validate_surface_envelope_receipt(target)


def test_surface_authority_or_metric_drift_is_rejected(tmp_path: Path) -> None:
    authority_target = write_receipt(tmp_path, surface_receipt(factualAuthority=True), "authority.json")
    with pytest.raises(SystemExit, match="authority boundary"):
        validate_surface_envelope_receipt(authority_target)

    metric_target = write_receipt(tmp_path, surface_receipt(metricRevision="changed"), "metric.json")
    with pytest.raises(SystemExit, match="metric revision drift"):
        validate_surface_envelope_receipt(metric_target)


def test_surface_ratio_floor_mismatch_is_rejected(tmp_path: Path) -> None:
    payload = surface_receipt()
    payload["productionSurface"]["ratioQuestionFloorWords"] = 4
    target = write_receipt(tmp_path, payload)
    with pytest.raises(SystemExit, match="ratio question floor mismatch"):
        validate_surface_envelope_receipt(target)


def test_surface_validator_recomputes_envelope_bounds(tmp_path: Path) -> None:
    payload = surface_receipt()
    payload["productionSurface"]["p90FloorNormalizedResponseToQuestionWordRatio"] = 3.0
    target = write_receipt(tmp_path, payload)
    with pytest.raises(SystemExit, match="normalized response/question ratio exceeds"):
        validate_surface_envelope_receipt(target)


def test_surface_validator_rejects_nonzero_assistantese_even_if_receipt_claims_pass(tmp_path: Path) -> None:
    payload = surface_receipt()
    payload["productionSurface"]["assistantesePrefixRate"] = 0.01
    target = write_receipt(tmp_path, payload)
    with pytest.raises(SystemExit, match="zero assistantese prefix rate"):
        validate_surface_envelope_receipt(target)


def test_direct_surface_pass_promotes_terminal_g6_receipt() -> None:
    machine = {
        "machineStatus": "MACHINE_ASSURANCE_PASS",
        "naturalnessQualification": "MEASURED_DOMAIN_GAP",
        "overallGateStatus": "CORPUS_NATURALNESS_QUALIFICATION_REQUIRED",
        "workflowSha": "candidate-sha",
    }
    semantic = validate_semantic_rejection()
    ontology = shared_ontology_receipt()
    surface = surface_receipt()
    finalized = finalize_receipt(machine, semantic, ontology, surface)

    assert finalized["machineStatus"] == "MACHINE_ASSURANCE_PASS"
    assert finalized["naturalnessQualification"] == "CORPUS_NATURALNESS_PASS"
    assert finalized["overallGateStatus"] == "G6_PASS"
    assert finalized["naturalnessReleaseOracle"] == "direct_production_surface_envelope"
    assert finalized["proxyModelTransferStatus"] == "DIAGNOSTIC_REJECTED_ARCHITECTURES_NOT_RELEASE_BLOCKING"
    assert finalized["semanticMatcherEvidence"] == "SEMANTIC_BRIDGE_TESTED_AND_REJECTED"
    summary = finalized["surfaceQualificationSummary"]
    assert summary["medianResponseWords"] == 11
    assert summary["p90ResponseWords"] == 11
    assert summary["p90FloorNormalizedResponseToQuestionWordRatio"] == 2.2
    assert summary["maximumHumanMedianResponseWords"] == 29.0
    assert summary["maximumHumanP90FloorNormalizedResponseToQuestionWordRatio"] == 2.5454545454545454
    assert summary["rendererModified"] is False
    assert summary["planningModified"] is True
