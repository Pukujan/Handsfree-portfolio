from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
TRANSITION_SCRIPT = ROOT / "scripts" / "verify_g6_multiwoz_transitions.py"
SPEC = importlib.util.spec_from_file_location("g6_multiwoz_transition", TRANSITION_SCRIPT)
assert SPEC and SPEC.loader
TRANSITIONS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TRANSITIONS
SPEC.loader.exec_module(TRANSITIONS)

EXPECTED_SOURCE_SHA = TRANSITIONS.EXPECTED_SOURCE_SHA
_TOKEN = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class UserTurnExample:
    text: str
    user_acts: tuple[str, ...]
    system_acts: tuple[str, ...]


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(text.lower()))


def iter_split_examples(root: Path, split: str, action_data: dict) -> Iterable[UserTurnExample]:
    for path in sorted((root / split).glob("dialogues_*.json")):
        dialogues = TRANSITIONS._load(path)
        for dialogue in dialogues:
            dialogue_id = str(dialogue["dialogue_id"])
            turns = dialogue.get("turns", [])
            for index in range(0, len(turns) - 1, 2):
                user = turns[index]
                system = turns[index + 1]
                if user.get("speaker") != "USER" or system.get("speaker") != "SYSTEM":
                    continue
                user_acts = TRANSITIONS._acts_for_turn(action_data, dialogue_id, index)
                system_acts = TRANSITIONS._acts_for_turn(action_data, dialogue_id, index + 1)
                if not user_acts or not system_acts:
                    continue
                yield UserTurnExample(
                    text=str(user.get("utterance", "")),
                    user_acts=user_acts,
                    system_acts=system_acts,
                )


class MultinomialLexicalActClassifier:
    """Small deterministic bag-of-words control; deliberately not an embedding model."""

    def __init__(self, *, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self.class_docs: Counter[str] = Counter()
        self.class_tokens: dict[str, Counter[str]] = defaultdict(Counter)
        self.class_token_totals: Counter[str] = Counter()
        self.vocabulary: set[str] = set()
        self._trained = False

    def fit(self, examples: Iterable[UserTurnExample]) -> "MultinomialLexicalActClassifier":
        for example in examples:
            tokens = tokenize(example.text)
            self.vocabulary.update(tokens)
            for label in example.user_acts:
                self.class_docs[label] += 1
                self.class_tokens[label].update(tokens)
                self.class_token_totals[label] += len(tokens)
        if not self.class_docs:
            raise ValueError("lexical classifier received no labelled examples")
        self._trained = True
        return self

    @property
    def classes(self) -> tuple[str, ...]:
        return tuple(sorted(self.class_docs))

    def predict(self, text: str) -> str:
        if not self._trained:
            raise RuntimeError("classifier must be fit before predict")
        tokens = tokenize(text)
        total_docs = sum(self.class_docs.values())
        class_count = len(self.class_docs)
        vocab_size = max(len(self.vocabulary), 1)
        best_label: str | None = None
        best_score = -math.inf
        for label in self.classes:
            prior = math.log((self.class_docs[label] + self.alpha) / (total_docs + self.alpha * class_count))
            denominator = self.class_token_totals[label] + self.alpha * vocab_size
            score = prior
            for token in tokens:
                score += math.log((self.class_tokens[label][token] + self.alpha) / denominator)
            if score > best_score or (score == best_score and (best_label is None or label < best_label)):
                best_label = label
                best_score = score
        assert best_label is not None
        return best_label


def evaluate_bridge(
    examples: Iterable[UserTurnExample],
    classifier: MultinomialLexicalActClassifier,
    global_system: Counter[str],
    edges: dict[str, Counter[str]],
) -> dict:
    system_fallback = TRANSITIONS._top(global_system)
    total = user_hits = graph_hits = graph_covered = baseline_hits = 0
    predicted_user_counts: Counter[str] = Counter()
    for example in examples:
        total += 1
        predicted_user = classifier.predict(example.text)
        predicted_user_counts[predicted_user] += 1
        user_hits += int(predicted_user in example.user_acts)
        baseline_hits += int(system_fallback in example.system_acts)
        graph_system, covered = TRANSITIONS.predict_graph((predicted_user,), edges, system_fallback)
        graph_covered += int(covered)
        graph_hits += int(graph_system in example.system_acts)
    if not total:
        raise ValueError("evaluation split produced no annotated user/system examples")
    baseline_accuracy = baseline_hits / total
    bridge_accuracy = graph_hits / total
    return {
        "testExampleCount": total,
        "userActTop1Accuracy": user_hits / total,
        "endToEndGraphTop1Accuracy": bridge_accuracy,
        "globalSystemActTop1Accuracy": baseline_accuracy,
        "endToEndGraphAbsoluteGain": bridge_accuracy - baseline_accuracy,
        "endToEndGraphCoverage": graph_covered / total,
        "predictedUserActCounts": dict(sorted(predicted_user_counts.items())),
    }


def main() -> None:
    root_value = os.environ.get("MULTIWOZ_ROOT")
    if not root_value:
        raise SystemExit("MULTIWOZ_ROOT is required")
    root = Path(root_value)
    source_sha = os.environ.get("MULTIWOZ_SHA", EXPECTED_SOURCE_SHA)
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"MultiWOZ revision mismatch: {source_sha} != {EXPECTED_SOURCE_SHA}")

    action_path = root / "dialog_acts.json"
    action_data = TRANSITIONS._load(action_path)

    train_examples = list(iter_split_examples(root, "dev", action_data))
    test_examples = list(iter_split_examples(root, "test", action_data))
    classifier = MultinomialLexicalActClassifier().fit(train_examples)

    global_system, edges, train_pair_count = TRANSITIONS.build_transition_model(
        TRANSITIONS.iter_split_pairs(root, "dev", action_data)
    )
    oracle_graph = TRANSITIONS.evaluate(
        TRANSITIONS.iter_split_pairs(root, "test", action_data), global_system, edges
    )
    bridge = evaluate_bridge(test_examples, classifier, global_system, edges)

    oracle_gain = oracle_graph["conditionalGraphAbsoluteGain"]
    e2e_gain = bridge["endToEndGraphAbsoluteGain"]
    gain_retention = e2e_gain / oracle_gain if oracle_gain > 0 else 0.0

    if e2e_gain >= 0.05 and bridge["endToEndGraphCoverage"] >= 0.90:
        semantic_evidence = "NOT_EARNED_YET_DETERMINISTIC_BRIDGE_SUFFICIENT"
    else:
        semantic_evidence = "MOTIVATED_BY_MEASURED_BRIDGE_FAILURE"

    receipt = {
        "status": "PASS",
        "source": "MultiWOZ-2.2",
        "sourceRevision": source_sha,
        "trainingSplit": "dev",
        "evaluationSplit": "test",
        "trainingExampleCount": len(train_examples),
        "testExampleCount": len(test_examples),
        "classifier": "multinomial_bag_of_words_naive_bayes",
        "classifierKind": "deterministic_lexical_baseline",
        "userActClassCount": len(classifier.classes),
        "vocabularySize": len(classifier.vocabulary),
        "oracleGraphTop1Accuracy": oracle_graph["conditionalGraphTop1Accuracy"],
        "oracleGraphAbsoluteGain": oracle_gain,
        "semanticMatcherEvidence": semantic_evidence,
        "graphRuntimeAdmission": "NOT_RUNTIME_ADMITTED",
        "rawDialogueEmitted": False,
        "factualAuthority": False,
        **bridge,
        "oracleGraphGainRetention": gain_retention,
        "trainingTransitionPairCount": train_pair_count,
    }

    target_value = os.environ.get("G6_UTTERANCE_BRIDGE_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
