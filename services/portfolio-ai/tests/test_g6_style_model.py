from __future__ import annotations

from collections import Counter, defaultdict
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "build_g6_style_model.py"
SPEC = importlib.util.spec_from_file_location("g6_style_model", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

BRIDGE = MODULE.BRIDGE
Example = MODULE.UserTurnExample


def _examples() -> list[Example]:
    return [
        Example("what area", ("request",), ("inform",)),
        Example("what price", ("request",), ("inform",)),
        Example("which area", ("request",), ("inform",)),
        Example("thanks", ("thank",), ("welcome",)),
        Example("thank you", ("thank",), ("welcome",)),
        Example("many thanks", ("thank",), ("welcome",)),
    ]


def _graph():
    global_system = Counter({"inform": 3, "welcome": 3})
    edges = defaultdict(Counter)
    edges["request"].update({"inform": 3})
    edges["thank"].update({"welcome": 3})
    return global_system, edges


def test_compact_classifier_payload_round_trips_predictions() -> None:
    classifier = MODULE._fit_with_min_token_count(_examples(), min_token_count=1)
    payload = MODULE._classifier_payload(classifier, min_token_count=1)
    restored = MODULE.classifier_from_payload(payload)
    for text in ("what area", "which price", "thanks", "thank you"):
        assert restored.predict(text) == classifier.predict(text)


def test_transition_payload_round_trips_counts() -> None:
    global_system, edges = _graph()
    payload = MODULE._transition_payload(global_system, edges)
    restored_global, restored_edges = MODULE.transition_model_from_payload(payload)
    assert restored_global == global_system
    assert restored_edges["request"] == edges["request"]
    assert restored_edges["thank"] == edges["thank"]


def test_compaction_chooses_first_predeclared_candidate_that_retains_behavior(monkeypatch) -> None:
    train = _examples() * 20
    test = _examples()
    global_system, edges = _graph()
    monkeypatch.setattr(MODULE, "CANDIDATE_MIN_TOKEN_COUNTS", (50, 20, 1))
    selected, metrics, candidates = MODULE.choose_compact_model(train, test, global_system, edges)
    assert candidates[-1]["minimumCorpusTokenCount"] == 1
    assert any(item["qualifies"] for item in candidates)
    assert len(selected.vocabulary) <= candidates[-1]["vocabularySize"]
    assert metrics["endToEndGraphCoverage"] == 1.0


def test_style_model_contract_is_explicitly_non_authoritative() -> None:
    classifier = MODULE._fit_with_min_token_count(_examples(), min_token_count=1)
    global_system, edges = _graph()
    model = {
        "modelVersion": "1.0.0",
        "authority": "style_only",
        "classifier": MODULE._classifier_payload(classifier, min_token_count=1),
        "transitionGraph": MODULE._transition_payload(global_system, edges),
        "renderingAuthority": {
            "mayCreateFacts": False,
            "mayCreateEvidence": False,
            "mayChangePackPermissions": False,
        },
    }
    assert model["authority"] == "style_only"
    assert not any(model["renderingAuthority"].values())
    encoded = MODULE._canonical_bytes(model).decode("utf-8")
    assert '"utterance"' not in encoded
    assert '"responseText"' not in encoded
