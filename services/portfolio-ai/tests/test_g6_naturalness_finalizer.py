from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.finalize_g6_naturalness_receipt import validate_semantic_rejection, validate_shared_ontology_receipt


def test_frozen_semantic_rejection_is_non_authoritative_and_below_admission_thresholds() -> None:
    receipt = validate_semantic_rejection()
    assert receipt["decision"] == "SEMANTIC_BRIDGE_NOT_EARNED"
    assert receipt["results"]["semanticMrdaUserActTop1Accuracy"] < receipt["selectionPolicy"]["minimumMrdaUserActTop1Accuracy"]
    assert receipt["results"]["mrdaAbsoluteImprovementOverLexical"] < receipt["selectionPolicy"]["minimumMrdaAbsoluteImprovementOverLexical"]
    assert not any(receipt["authority"].values())


def test_shared_ontology_finalizer_rejects_authority_drift(tmp_path: Path) -> None:
    payload = {
        "status": "PASS",
        "sourceRevisions": {
            "multiwoz": "fe0c8e65cfcd8462bd33c86e35f21addc84ca82b",
            "mrda": "58006b32d4e36ca518e365899924cd56035466a2",
        },
        "rawDialogueEmitted": False,
        "factualAuthority": True,
        "selectionPolicy": {
            "minimumGraphCoverage": 0.9,
            "minimumMrdaBalancedAccuracy": 0.75,
            "minimumMrdaQueryRecall": 0.65,
            "minimumMultiwozBalancedAccuracy": 0.75,
            "minimumRelativeNllImprovement": 0.02,
        },
    }
    target = tmp_path / "ontology.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SystemExit, match="style-only authority boundary"):
        validate_shared_ontology_receipt(target)


def test_shared_ontology_finalizer_rejects_threshold_drift(tmp_path: Path) -> None:
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
            "minimumMrdaBalancedAccuracy": 0.70,
            "minimumMrdaQueryRecall": 0.65,
            "minimumMultiwozBalancedAccuracy": 0.75,
            "minimumRelativeNllImprovement": 0.02,
        },
    }
    target = tmp_path / "ontology.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SystemExit, match="selection policy drift"):
        validate_shared_ontology_receipt(target)
