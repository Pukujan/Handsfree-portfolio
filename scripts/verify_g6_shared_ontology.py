from __future__ import annotations

from collections import Counter, defaultdict
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
from typing import Iterable, Protocol

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SCRIPT = ROOT / "scripts" / "verify_g6_multiwoz_utterance_bridge.py"
MRDA_SCRIPT = ROOT / "scripts" / "verify_g6_mrda_transfer.py"

BRIDGE_SPEC = importlib.util.spec_from_file_location("g6_bridge_for_shared_ontology", BRIDGE_SCRIPT)
assert BRIDGE_SPEC and BRIDGE_SPEC.loader
BRIDGE = importlib.util.module_from_spec(BRIDGE_SPEC)
sys.modules[BRIDGE_SPEC.name] = BRIDGE
BRIDGE_SPEC.loader.exec_module(BRIDGE)

MRDA_SPEC = importlib.util.spec_from_file_location("g6_mrda_for_shared_ontology", MRDA_SCRIPT)
assert MRDA_SPEC and MRDA_SPEC.loader
MRDA = importlib.util.module_from_spec(MRDA_SPEC)
sys.modules[MRDA_SPEC.name] = MRDA
MRDA_SPEC.loader.exec_module(MRDA)

QUERY = "QUERY"
OTHER = "OTHER"
CONTENT = "CONTENT"
ACK = "ACK"
TURN = "TURN_MANAGEMENT"
RESPONSE_MOVES = (ACK, CONTENT, QUERY, TURN)

MIN_MRDA_BALANCED_ACCURACY = 0.75
MIN_MRDA_QUERY_RECALL = 0.65
MIN_MULTIWOZ_BALANCED_ACCURACY = 0.75
MIN_RELATIVE_NLL_IMPROVEMENT = 0.02
MIN_GRAPH_COVERAGE = 0.90
SMOOTHING_ALPHA = 1.0

QUESTION_INITIAL_TOKENS = {
    "am", "are", "can", "could", "did", "do", "does", "had", "has", "have",
    "how", "is", "may", "might", "must", "should", "was", "were", "what", "when",
    "where", "which", "who", "whom", "whose", "why", "will", "would",
}


class QueryClassifier(Protocol):
    def predict(self, text: str) -> str: ...


class StructuralQueryClassifier:
    """Corpus-neutral question cue baseline; no learned parameters."""

    def predict(self, text: str) -> str:
        stripped = text.strip().lower()
        tokens = BRIDGE.tokenize(stripped)
        if stripped.endswith("?"):
            return QUERY
        if tokens and tokens[0] in QUESTION_INITIAL_TOKENS:
            return QUERY
        return OTHER


def canonical_multiwoz_user_move(acts: Iterable[str]) -> str:
    return QUERY if "request" in set(acts) else OTHER


def canonical_mrda_user_move(basic_act: str) -> str:
    return QUERY if basic_act == "Q" else OTHER


def canonical_mrda_response_move(basic_act: str) -> str:
    if basic_act == "S":
        return CONTENT
    if basic_act == "Q":
        return QUERY
    if basic_act == "B":
        return ACK
    if basic_act in {"D", "F"}:
        return TURN
    raise ValueError(f"unexpected MRDA basic act: {basic_act}")


def canonical_mrda_full_source_move(basic_act: str) -> str:
    return canonical_mrda_response_move(basic_act)


def binary_training_examples(examples: Iterable[object]) -> tuple[object, ...]:
    return tuple(
        BRIDGE.UserTurnExample(
            text=example.text,
            user_acts=(canonical_multiwoz_user_move(example.user_acts),),
            system_acts=example.system_acts,
        )
        for example in examples
    )


def evaluate_binary(expected: Iterable[str], predicted: Iterable[str]) -> dict:
    expected = tuple(expected)
    predicted = tuple(predicted)
    if len(expected) != len(predicted) or not expected:
        raise ValueError("binary evaluation shape mismatch")
    counts: Counter[str] = Counter()
    for truth, guess in zip(expected, predicted, strict=True):
        if truth not in {QUERY, OTHER} or guess not in {QUERY, OTHER}:
            raise ValueError("binary evaluation received non-canonical label")
        counts[f"{truth}->{guess}"] += 1
    query_total = sum(counts[f"{QUERY}->{guess}"] for guess in (QUERY, OTHER))
    other_total = sum(counts[f"{OTHER}->{guess}"] for guess in (QUERY, OTHER))
    query_recall = counts[f"{QUERY}->{QUERY}"] / query_total if query_total else 0.0
    other_recall = counts[f"{OTHER}->{OTHER}"] / other_total if other_total else 0.0
    accuracy = (
        counts[f"{QUERY}->{QUERY}"] + counts[f"{OTHER}->{OTHER}"]
    ) / len(expected)
    return {
        "exampleCount": len(expected),
        "accuracy": accuracy,
        "balancedAccuracy": (query_recall + other_recall) / 2,
        "queryRecall": query_recall,
        "otherRecall": other_recall,
        "confusion": dict(sorted(counts.items())),
    }


def evaluate_multiwoz_classifier(examples: Iterable[object], classifier: QueryClassifier) -> dict:
    examples = tuple(examples)
    return evaluate_binary(
        (canonical_multiwoz_user_move(example.user_acts) for example in examples),
        (classifier.predict(example.text) for example in examples),
    )


def evaluate_mrda_classifier(pairs: Iterable[tuple[object, object]], classifier: QueryClassifier) -> dict:
    pairs = tuple(pairs)
    return evaluate_binary(
        (canonical_mrda_user_move(source.basic_act) for source, _target in pairs),
        (classifier.predict(source.text) for source, _target in pairs),
    )


def classifier_qualifies(mrda_metrics: dict, multiwoz_metrics: dict) -> bool:
    return (
        mrda_metrics["balancedAccuracy"] >= MIN_MRDA_BALANCED_ACCURACY
        and mrda_metrics["queryRecall"] >= MIN_MRDA_QUERY_RECALL
        and multiwoz_metrics["balancedAccuracy"] >= MIN_MULTIWOZ_BALANCED_ACCURACY
    )


def build_distribution_model(
    pairs: Iterable[tuple[object, object]],
    source_mapper,
) -> tuple[Counter[str], dict[str, Counter[str]]]:
    global_counts: Counter[str] = Counter()
    conditional: dict[str, Counter[str]] = defaultdict(Counter)
    for source, target in pairs:
        target_move = canonical_mrda_response_move(target.basic_act)
        source_move = source_mapper(source)
        global_counts[target_move] += 1
        conditional[source_move][target_move] += 1
    if not global_counts:
        raise ValueError("distribution graph received no training pairs")
    return global_counts, conditional


def probability(counts: Counter[str], move: str) -> float:
    denominator = sum(counts.values()) + SMOOTHING_ALPHA * len(RESPONSE_MOVES)
    return (counts[move] + SMOOTHING_ALPHA) / denominator


def evaluate_distribution_graph(
    pairs: Iterable[tuple[object, object]],
    *,
    global_counts: Counter[str],
    conditional: dict[str, Counter[str]],
    source_mapper,
) -> dict:
    total = 0
    global_nll = 0.0
    graph_nll = 0.0
    covered = 0
    for source, target in pairs:
        total += 1
        target_move = canonical_mrda_response_move(target.basic_act)
        global_nll -= math.log(probability(global_counts, target_move))
        source_move = source_mapper(source)
        edge_counts = conditional.get(source_move)
        if edge_counts:
            covered += 1
            graph_nll -= math.log(probability(edge_counts, target_move))
        else:
            graph_nll -= math.log(probability(global_counts, target_move))
    if not total:
        raise ValueError("distribution graph evaluation received no pairs")
    global_nll /= total
    graph_nll /= total
    relative = (global_nll - graph_nll) / global_nll if global_nll > 0 else 0.0
    return {
        "pairCount": total,
        "globalNegativeLogLikelihood": global_nll,
        "conditionalNegativeLogLikelihood": graph_nll,
        "relativeNllImprovement": relative,
        "coverage": covered / total,
    }


def graph_qualifies(metrics: dict) -> bool:
    return (
        metrics["relativeNllImprovement"] >= MIN_RELATIVE_NLL_IMPROVEMENT
        and metrics["coverage"] >= MIN_GRAPH_COVERAGE
    )


def main() -> None:
    multiwoz_root_value = os.environ.get("MULTIWOZ_ROOT")
    mrda_root_value = os.environ.get("MRDA_ROOT")
    if not multiwoz_root_value or not mrda_root_value:
        raise SystemExit("MULTIWOZ_ROOT and MRDA_ROOT are required")
    if os.environ.get("MULTIWOZ_SHA", BRIDGE.EXPECTED_SOURCE_SHA) != BRIDGE.EXPECTED_SOURCE_SHA:
        raise SystemExit("MultiWOZ revision mismatch")
    if os.environ.get("MRDA_SHA", MRDA.EXPECTED_MRDA_SHA) != MRDA.EXPECTED_MRDA_SHA:
        raise SystemExit("MRDA revision mismatch")

    multiwoz_root = Path(multiwoz_root_value)
    action_data = BRIDGE.TRANSITIONS._load(multiwoz_root / "dialog_acts.json")
    mw_train = list(BRIDGE.iter_split_examples(multiwoz_root, "dev", action_data))
    mw_test = list(BRIDGE.iter_split_examples(multiwoz_root, "test", action_data))

    structural = StructuralQueryClassifier()
    lexical = BRIDGE.MultinomialLexicalActClassifier().fit(binary_training_examples(mw_train))

    mrda_root = Path(mrda_root_value)
    mrda_train_pairs = MRDA.cross_speaker_pairs(MRDA.load_turns(mrda_root / "train_set.txt"))
    mrda_test_pairs = MRDA.cross_speaker_pairs(MRDA.load_turns(mrda_root / "test_set.txt"))

    candidate_metrics = []
    selected_name: str | None = None
    selected_classifier: QueryClassifier | None = None
    for name, classifier in (("structural_question_cues", structural), ("binary_multiwoz_lexical_nb", lexical)):
        mw_metrics = evaluate_multiwoz_classifier(mw_test, classifier)
        mrda_metrics = evaluate_mrda_classifier(mrda_test_pairs, classifier)
        qualifies = classifier_qualifies(mrda_metrics, mw_metrics)
        candidate_metrics.append(
            {
                "classifier": name,
                "qualifies": qualifies,
                "multiwoz": mw_metrics,
                "mrda": mrda_metrics,
            }
        )
        if selected_classifier is None and qualifies:
            selected_name = name
            selected_classifier = classifier

    full_global, full_edges = build_distribution_model(
        mrda_train_pairs,
        lambda source: canonical_mrda_full_source_move(source.basic_act),
    )
    oracle_full_graph = evaluate_distribution_graph(
        mrda_test_pairs,
        global_counts=full_global,
        conditional=full_edges,
        source_mapper=lambda source: canonical_mrda_full_source_move(source.basic_act),
    )

    binary_global, binary_edges = build_distribution_model(
        mrda_train_pairs,
        lambda source: canonical_mrda_user_move(source.basic_act),
    )
    binary_oracle_graph = evaluate_distribution_graph(
        mrda_test_pairs,
        global_counts=binary_global,
        conditional=binary_edges,
        source_mapper=lambda source: canonical_mrda_user_move(source.basic_act),
    )

    selected_graph = None
    if selected_classifier is not None:
        selected_graph = evaluate_distribution_graph(
            mrda_test_pairs,
            global_counts=binary_global,
            conditional=binary_edges,
            source_mapper=lambda source: selected_classifier.predict(source.text),
        )

    ontology_bridge_evidence = (
        "SHARED_ONTOLOGY_BRIDGE_EARNED"
        if selected_classifier is not None
        else "SHARED_ONTOLOGY_BRIDGE_NOT_EARNED"
    )
    full_graph_evidence = (
        "DISTRIBUTIONAL_DISCOURSE_GRAPH_EARNED"
        if graph_qualifies(oracle_full_graph)
        else "DISTRIBUTIONAL_DISCOURSE_GRAPH_NOT_EARNED"
    )
    runtime_graph_evidence = (
        "BINARY_RUNTIME_GRAPH_EARNED"
        if selected_graph is not None and graph_qualifies(selected_graph)
        else "BINARY_RUNTIME_GRAPH_NOT_EARNED"
    )

    receipt = {
        "status": "PASS",
        "experimentKind": "shared_dialogue_ontology_and_distributional_graph",
        "sourceRevisions": {
            "multiwoz": BRIDGE.EXPECTED_SOURCE_SHA,
            "mrda": MRDA.EXPECTED_MRDA_SHA,
        },
        "ontology": {
            "userMoves": [OTHER, QUERY],
            "responseMoves": list(RESPONSE_MOVES),
            "mrdaTurnManagementMapping": ["D", "F"],
        },
        "classifierSelectionOrder": ["structural_question_cues", "binary_multiwoz_lexical_nb"],
        "selectionPolicy": {
            "minimumMrdaBalancedAccuracy": MIN_MRDA_BALANCED_ACCURACY,
            "minimumMrdaQueryRecall": MIN_MRDA_QUERY_RECALL,
            "minimumMultiwozBalancedAccuracy": MIN_MULTIWOZ_BALANCED_ACCURACY,
            "minimumRelativeNllImprovement": MIN_RELATIVE_NLL_IMPROVEMENT,
            "minimumGraphCoverage": MIN_GRAPH_COVERAGE,
        },
        "classifierCandidates": candidate_metrics,
        "selectedClassifier": selected_name,
        "ontologyBridgeEvidence": ontology_bridge_evidence,
        "oracleFullMoveDistributionGraph": oracle_full_graph,
        "binaryOracleDistributionGraph": binary_oracle_graph,
        "selectedClassifierDistributionGraph": selected_graph,
        "distributionalGraphEvidence": full_graph_evidence,
        "runtimeGraphEvidence": runtime_graph_evidence,
        "semanticBridgeEvidence": "TESTED_AND_REJECTED_BY_PRIOR_PINNED_EXPERIMENT",
        "rawDialogueEmitted": False,
        "factualAuthority": False,
    }

    target_value = os.environ.get("G6_SHARED_ONTOLOGY_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
