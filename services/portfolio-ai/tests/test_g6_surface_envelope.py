from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_g6_surface_envelope.py"
SPEC = importlib.util.spec_from_file_location("g6_surface_envelope", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_surface_metrics_detect_assistantese_and_unsolicited_closings() -> None:
    assert MODULE.starts_with_assistantese("Certainly, here is the answer.")
    assert MODULE.has_unsolicited_closing("The answer is X. Would you like me to explain more?")
    assert MODULE.has_heading_or_list("1. First\n2. Second")
    assert not MODULE.starts_with_assistantese("FOSSIL keeps durable evidence canonical.")


def test_open_comparison_question_does_not_justify_correction_prefix() -> None:
    question = "Why not just use Neo4j?"
    answer = "Not quite. Neo4j is a replaceable projection."
    assert not MODULE.explicit_premise_challenge(question)
    assert MODULE.misapplied_correction(question, answer)


def test_explicit_false_premise_can_use_correction_prefix() -> None:
    question = "I thought Neo4j was the durable authority."
    answer = "Not quite. Neo4j is a replaceable projection."
    assert MODULE.explicit_premise_challenge(question)
    assert not MODULE.misapplied_correction(question, answer)


def test_surface_envelope_uses_human_percentiles_and_zero_assistantese_policy() -> None:
    multiwoz = {
        "pairCount": 200,
        "p95ResponseWords": 25.0,
        "p90ResponseToQuestionWordRatio": 4.0,
    }
    mrda = {
        "pairCount": 200,
        "p95ResponseWords": 20.0,
        "p90ResponseToQuestionWordRatio": 3.0,
    }
    production = {
        "medianResponseWords": 20.0,
        "p90ResponseToQuestionWordRatio": 3.5,
        "assistantesePrefixRate": 0.0,
        "unsolicitedClosingRate": 0.0,
        "headingOrListRate": 0.0,
        "misappliedCorrectionRate": 0.0,
    }
    status, defects, envelope = MODULE.evaluate_surface_envelope(production, multiwoz, mrda)
    assert status == "PASS"
    assert defects == []
    assert envelope["maximumMedianResponseWords"] == 25.0
    assert envelope["maximumP90ResponseToQuestionWordRatio"] == 4.0


def test_surface_envelope_reports_specific_defects_without_changing_renderer() -> None:
    human = {
        "pairCount": 200,
        "p95ResponseWords": 20.0,
        "p90ResponseToQuestionWordRatio": 3.0,
    }
    production = {
        "medianResponseWords": 21.0,
        "p90ResponseToQuestionWordRatio": 4.0,
        "assistantesePrefixRate": 0.0,
        "unsolicitedClosingRate": 0.0,
        "headingOrListRate": 0.0,
        "misappliedCorrectionRate": 0.1,
    }
    status, defects, _ = MODULE.evaluate_surface_envelope(production, human, human)
    assert status == "MEASURED_SURFACE_DEFECT"
    assert defects == [
        "MEDIAN_RESPONSE_OVER_HUMAN_P95",
        "RESPONSE_TO_QUESTION_RATIO_ABOVE_HUMAN_P90",
        "MISAPPLIED_CORRECTION_FRAMING",
    ]
