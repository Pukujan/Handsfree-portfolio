from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_g6_mrda_transfer.py"
SPEC = importlib.util.spec_from_file_location("g6_mrda_transfer", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

MrdaTurn = MODULE.MrdaTurn


def test_mrda_parser_preserves_five_field_contract() -> None:
    turn = MODULE.parse_mrda_line("spk1|what happened?|Q|qw|qw")
    assert turn == MrdaTurn("spk1", "what happened?", "Q", "qw", "qw")


def test_cross_speaker_pairs_exclude_same_speaker_continuations() -> None:
    turns = (
        MrdaTurn("a", "one", "S", "s", "s"),
        MrdaTurn("a", "two", "S", "s", "s"),
        MrdaTurn("b", "three", "B", "b", "b"),
        MrdaTurn("a", "four", "Q", "qy", "qy"),
    )
    pairs = MODULE.cross_speaker_pairs(turns)
    assert [(left.text, right.text) for left, right in pairs] == [("two", "three"), ("three", "four")]


def test_cross_domain_mapping_is_fixed_before_measurement() -> None:
    assert MODULE.expected_multiwoz_user_act("Q") == "request"
    assert MODULE.expected_multiwoz_user_act("S") == "inform"
    assert MODULE.expected_multiwoz_user_act("B") is None
    assert MODULE.model_system_act_to_mrda_basic("request") == "Q"
    assert MODULE.model_system_act_to_mrda_basic("bye") == "B"
    assert MODULE.model_system_act_to_mrda_basic("inform") == "S"
    assert MODULE.REPRESENTABLE_BASIC_RESPONSE_ACTS == {"S", "Q", "B"}


def test_native_graph_measurement_compares_against_training_majority() -> None:
    train_pairs = (
        (MrdaTurn("a", "q1", "Q", "qy", "qy"), MrdaTurn("b", "a1", "S", "s", "s")),
        (MrdaTurn("a", "q2", "Q", "qy", "qy"), MrdaTurn("b", "a2", "S", "s", "s")),
        (MrdaTurn("a", "s1", "S", "s", "s"), MrdaTurn("b", "q3", "Q", "qy", "qy")),
        (MrdaTurn("a", "s2", "S", "s", "s"), MrdaTurn("b", "q4", "Q", "qy", "qy")),
        (MrdaTurn("a", "s3", "S", "s", "s"), MrdaTurn("b", "q5", "Q", "qy", "qy")),
    )
    global_responses, edges = MODULE.build_native_graph(train_pairs)
    assert global_responses == Counter({"Q": 3, "S": 2})
    result = MODULE.evaluate_native_graph(train_pairs, global_responses, edges)
    assert result["conditionalGraphTop1Accuracy"] == 1.0
    assert result["conditionalGraphTop1Accuracy"] > result["globalBaselineTop1Accuracy"]


def test_current_style_model_cannot_claim_full_mrda_move_coverage() -> None:
    target_counts = Counter({"S": 6, "B": 2, "Q": 1, "F": 1})
    representable = sum(target_counts[label] for label in MODULE.REPRESENTABLE_BASIC_RESPONSE_ACTS)
    assert representable / sum(target_counts.values()) == 0.9
    assert "F" not in MODULE.REPRESENTABLE_BASIC_RESPONSE_ACTS
    assert "D" not in MODULE.REPRESENTABLE_BASIC_RESPONSE_ACTS
