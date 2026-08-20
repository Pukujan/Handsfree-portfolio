from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_g6_shared_ontology.py"
SPEC = importlib.util.spec_from_file_location("g6_shared_ontology", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_shared_ontology_is_small_and_turn_management_stays_non_factual() -> None:
    assert MODULE.canonical_mrda_user_move("Q") == MODULE.QUERY
    for basic in ("S", "B", "D", "F"):
        assert MODULE.canonical_mrda_user_move(basic) == MODULE.OTHER
    assert MODULE.canonical_mrda_response_move("S") == MODULE.CONTENT
    assert MODULE.canonical_mrda_response_move("Q") == MODULE.QUERY
    assert MODULE.canonical_mrda_response_move("B") == MODULE.ACK
    assert MODULE.canonical_mrda_response_move("D") == MODULE.TURN
    assert MODULE.canonical_mrda_response_move("F") == MODULE.TURN


def test_structural_question_classifier_is_deterministic_and_corpus_neutral() -> None:
    classifier = MODULE.StructuralQueryClassifier()
    assert classifier.predict("What did you build?") == MODULE.QUERY
    assert classifier.predict("Can you explain that") == MODULE.QUERY
    assert classifier.predict("I built the ingestion path.") == MODULE.OTHER


def test_classifier_admission_requires_all_predeclared_thresholds() -> None:
    passing_mrda = {"balancedAccuracy": 0.80, "queryRecall": 0.70}
    passing_multiwoz = {"balancedAccuracy": 0.80}
    assert MODULE.classifier_qualifies(passing_mrda, passing_multiwoz)
    assert not MODULE.classifier_qualifies({"balancedAccuracy": 0.74, "queryRecall": 0.90}, passing_multiwoz)
    assert not MODULE.classifier_qualifies({"balancedAccuracy": 0.90, "queryRecall": 0.64}, passing_multiwoz)
    assert not MODULE.classifier_qualifies(passing_mrda, {"balancedAccuracy": 0.74})


def test_distribution_graph_admission_uses_nll_not_top1() -> None:
    assert MODULE.graph_qualifies({"relativeNllImprovement": 0.021, "coverage": 0.95})
    assert not MODULE.graph_qualifies({"relativeNllImprovement": 0.019, "coverage": 1.0})
    assert not MODULE.graph_qualifies({"relativeNllImprovement": 0.10, "coverage": 0.89})


def test_binary_metrics_are_balanced_against_class_imbalance() -> None:
    metrics = MODULE.evaluate_binary(
        [MODULE.QUERY, MODULE.QUERY, MODULE.OTHER, MODULE.OTHER, MODULE.OTHER, MODULE.OTHER],
        [MODULE.QUERY, MODULE.OTHER, MODULE.OTHER, MODULE.OTHER, MODULE.OTHER, MODULE.OTHER],
    )
    assert metrics["queryRecall"] == 0.5
    assert metrics["otherRecall"] == 1.0
    assert metrics["balancedAccuracy"] == 0.75
