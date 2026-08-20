from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_g6_semantic_transfer.py"
SPEC = importlib.util.spec_from_file_location("g6_semantic_transfer", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_semantic_experiment_is_pinned_and_evaluation_only() -> None:
    assert MODULE.SEMANTIC_MODEL_ID == "sentence-transformers/all-MiniLM-L6-v2"
    assert MODULE.SEMANTIC_MODEL_REVISION == "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    assert MODULE.SENTENCE_TRANSFORMERS_VERSION == "5.6.1"
    assert MODULE.MIN_MRDA_USER_ACT_ACCURACY == 0.80
    assert MODULE.MIN_MRDA_ABSOLUTE_IMPROVEMENT == 0.20
    assert MODULE.MIN_MULTIWOZ_USER_ACT_ACCURACY == 0.80


def test_semantic_bridge_is_earned_only_when_all_predeclared_thresholds_pass() -> None:
    earned = MODULE.decide_semantic_admission(
        mrda_user_act_accuracy=0.85,
        lexical_mrda_user_act_accuracy=0.20,
        multiwoz_user_act_accuracy=0.88,
    )
    assert earned == "SEMANTIC_BRIDGE_EARNED_FOR_USER_ACT_CLASSIFICATION_ONLY"

    assert MODULE.decide_semantic_admission(
        mrda_user_act_accuracy=0.79,
        lexical_mrda_user_act_accuracy=0.20,
        multiwoz_user_act_accuracy=0.90,
    ) == "SEMANTIC_BRIDGE_NOT_EARNED"
    assert MODULE.decide_semantic_admission(
        mrda_user_act_accuracy=0.85,
        lexical_mrda_user_act_accuracy=0.70,
        multiwoz_user_act_accuracy=0.90,
    ) == "SEMANTIC_BRIDGE_NOT_EARNED"
    assert MODULE.decide_semantic_admission(
        mrda_user_act_accuracy=0.85,
        lexical_mrda_user_act_accuracy=0.20,
        multiwoz_user_act_accuracy=0.79,
    ) == "SEMANTIC_BRIDGE_NOT_EARNED"
