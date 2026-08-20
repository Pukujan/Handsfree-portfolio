from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_g6_multiwoz_transitions.py"
SPEC = importlib.util.spec_from_file_location("g6_multiwoz", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

TurnPair = MODULE.TurnPair
build_transition_model = MODULE.build_transition_model
evaluate = MODULE.evaluate
predict_graph = MODULE.predict_graph


def test_conditional_transition_graph_beats_global_majority_on_structured_human_acts() -> None:
    train = [
        TurnPair(("request",), ("inform",), 4, 5),
        TurnPair(("request",), ("inform",), 3, 4),
        TurnPair(("thank",), ("welcome",), 2, 2),
        TurnPair(("thank",), ("welcome",), 2, 1),
        TurnPair(("greet",), ("greet",), 1, 1),
    ]
    global_system, edges, count = build_transition_model(train)
    assert count == 5
    test = [
        TurnPair(("request",), ("inform",), 4, 5),
        TurnPair(("thank",), ("welcome",), 2, 2),
        TurnPair(("greet",), ("greet",), 1, 1),
    ]
    metrics = evaluate(test, global_system, edges)
    assert metrics["conditionalGraphTop1Accuracy"] == 1.0
    assert metrics["conditionalGraphTop1Accuracy"] > metrics["globalBaselineTop1Accuracy"]


def test_unknown_user_act_falls_back_without_inventing_transition() -> None:
    global_system, edges, _ = build_transition_model([
        TurnPair(("request",), ("inform",), 2, 3),
    ])
    predicted, covered = predict_graph(("unknown",), edges, "inform")
    assert predicted == "inform"
    assert covered is False


def test_act_family_is_domain_agnostic() -> None:
    assert MODULE._act_family("Hotel-Inform") == "inform"
    assert MODULE._act_family("general-greet") == "greet"


def test_receipt_design_contains_no_utterance_field() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"rawDialogueEmitted": False' in source
    assert '"utterance"' not in source.split("receipt = {", 1)[1]
