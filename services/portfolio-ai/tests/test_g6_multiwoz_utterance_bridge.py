from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_g6_multiwoz_utterance_bridge.py"
SPEC = importlib.util.spec_from_file_location("g6_multiwoz_bridge", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

Example = MODULE.UserTurnExample
Classifier = MODULE.MultinomialLexicalActClassifier
evaluate_bridge = MODULE.evaluate_bridge
TRANSITIONS = MODULE.TRANSITIONS


def test_lexical_classifier_learns_obvious_dialogue_act_words() -> None:
    train = [
        Example("what area is it in", ("request",), ("inform",)),
        Example("what price range", ("request",), ("inform",)),
        Example("thanks a lot", ("thank",), ("welcome",)),
        Example("thank you", ("thank",), ("welcome",)),
    ]
    classifier = Classifier().fit(train)
    assert classifier.predict("thanks") == "thank"
    assert classifier.predict("what area") == "request"


def test_lexical_classifier_tie_break_is_deterministic() -> None:
    classifier = Classifier().fit([
        Example("same", ("alpha",), ("inform",)),
        Example("same", ("beta",), ("inform",)),
    ])
    assert classifier.predict("same") == "alpha"


def test_end_to_end_bridge_can_preserve_graph_advantage() -> None:
    train = [
        Example("where is it", ("request",), ("inform",)),
        Example("what price", ("request",), ("inform",)),
        Example("thanks", ("thank",), ("welcome",)),
        Example("thank you", ("thank",), ("welcome",)),
    ]
    classifier = Classifier().fit(train)
    global_system, edges, _ = TRANSITIONS.build_transition_model([
        TRANSITIONS.TurnPair(("request",), ("inform",), 3, 4),
        TRANSITIONS.TurnPair(("request",), ("inform",), 3, 4),
        TRANSITIONS.TurnPair(("thank",), ("welcome",), 2, 2),
        TRANSITIONS.TurnPair(("thank",), ("welcome",), 2, 2),
    ])
    metrics = evaluate_bridge([
        Example("what area", ("request",), ("inform",)),
        Example("thanks", ("thank",), ("welcome",)),
    ], classifier, global_system, edges)
    assert metrics["userActTop1Accuracy"] == 1.0
    assert metrics["endToEndGraphTop1Accuracy"] == 1.0
    assert metrics["endToEndGraphTop1Accuracy"] > metrics["globalSystemActTop1Accuracy"]


def test_receipt_never_emits_raw_dialogue_text() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    receipt_source = source.split("receipt = {", 1)[1]
    assert '"rawDialogueEmitted": False' in receipt_source
    assert '"text"' not in receipt_source
    assert '"utterance"' not in receipt_source
    assert '"factualAuthority": False' in receipt_source
