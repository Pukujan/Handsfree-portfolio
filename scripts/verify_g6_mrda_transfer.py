from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
STYLE_SCRIPT = ROOT / "scripts" / "build_g6_style_model.py"
SPEC = importlib.util.spec_from_file_location("g6_style_model_for_mrda_transfer", STYLE_SCRIPT)
assert SPEC and SPEC.loader
STYLE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = STYLE
SPEC.loader.exec_module(STYLE)

EXPECTED_MRDA_SHA = "58006b32d4e36ca518e365899924cd56035466a2"
MIN_REPRESENTABLE_TARGET_COVERAGE = 0.90
MIN_SCORABLE_USER_ACT_ACCURACY = 0.80
MIN_TRANSFER_GAIN = 0.02
MIN_NATIVE_GRAPH_GAIN = 0.02
MIN_NATIVE_GRAPH_COVERAGE = 0.90

QUESTION_SYSTEM_ACTS = {"request", "reqmore"}
BACKCHANNEL_SYSTEM_ACTS = {"bye", "greet", "thank", "welcome"}
REPRESENTABLE_BASIC_RESPONSE_ACTS = {"S", "Q", "B"}


@dataclass(frozen=True)
class MrdaTurn:
    speaker: str
    text: str
    basic_act: str
    general_act: str
    full_act: str


def parse_mrda_line(line: str) -> MrdaTurn:
    parts = line.rstrip("\n").split("|", 4)
    if len(parts) != 5:
        raise ValueError(f"invalid MRDA line with {len(parts)} fields")
    speaker, text, basic_act, general_act, full_act = parts
    if basic_act not in {"S", "B", "D", "F", "Q"}:
        raise ValueError(f"unexpected MRDA basic act: {basic_act}")
    return MrdaTurn(speaker, text, basic_act, general_act, full_act)


def load_turns(path: Path) -> tuple[MrdaTurn, ...]:
    return tuple(
        parse_mrda_line(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def cross_speaker_pairs(turns: Iterable[MrdaTurn]) -> tuple[tuple[MrdaTurn, MrdaTurn], ...]:
    turns = tuple(turns)
    return tuple(
        (current, following)
        for current, following in zip(turns, turns[1:])
        if current.speaker != following.speaker
    )


def deterministic_top(counts: Counter[str]) -> str:
    if not counts:
        raise ValueError("cannot choose from empty counts")
    return min(counts, key=lambda label: (-counts[label], label))


def build_native_graph(
    pairs: Iterable[tuple[MrdaTurn, MrdaTurn]],
) -> tuple[Counter[str], dict[str, Counter[str]]]:
    global_responses: Counter[str] = Counter()
    edges: dict[str, Counter[str]] = defaultdict(Counter)
    for source, target in pairs:
        global_responses[target.basic_act] += 1
        edges[source.basic_act][target.basic_act] += 1
    if not global_responses:
        raise ValueError("MRDA training pairs are empty")
    return global_responses, edges


def evaluate_native_graph(
    pairs: Iterable[tuple[MrdaTurn, MrdaTurn]],
    global_responses: Counter[str],
    edges: dict[str, Counter[str]],
) -> dict:
    baseline = deterministic_top(global_responses)
    total = baseline_hits = graph_hits = covered = 0
    for source, target in pairs:
        total += 1
        baseline_hits += int(target.basic_act == baseline)
        if source.basic_act in edges and edges[source.basic_act]:
            prediction = deterministic_top(edges[source.basic_act])
            covered += 1
        else:
            prediction = baseline
        graph_hits += int(target.basic_act == prediction)
    if not total:
        raise ValueError("MRDA evaluation pairs are empty")
    baseline_accuracy = baseline_hits / total
    graph_accuracy = graph_hits / total
    return {
        "pairCount": total,
        "globalBaselinePrediction": baseline,
        "globalBaselineTop1Accuracy": baseline_accuracy,
        "conditionalGraphTop1Accuracy": graph_accuracy,
        "conditionalGraphAbsoluteGain": graph_accuracy - baseline_accuracy,
        "conditionalGraphCoverage": covered / total,
    }


def expected_multiwoz_user_act(basic_act: str) -> str | None:
    if basic_act == "Q":
        return "request"
    if basic_act == "S":
        return "inform"
    return None


def model_system_act_to_mrda_basic(system_act: str) -> str:
    if system_act in QUESTION_SYSTEM_ACTS:
        return "Q"
    if system_act in BACKCHANNEL_SYSTEM_ACTS:
        return "B"
    return "S"


def evaluate_current_style_model(
    pairs: Iterable[tuple[MrdaTurn, MrdaTurn]],
    model: dict,
    *,
    mrda_baseline_act: str,
) -> dict:
    if model.get("authority") != "style_only":
        raise ValueError("style model must remain non-authoritative")
    if any(model.get("renderingAuthority", {}).values()):
        raise ValueError("style model rendering authority must remain false")

    classifier = STYLE.classifier_from_payload(model["classifier"])
    multiwoz_global, multiwoz_edges = STYLE.transition_model_from_payload(model["transitionGraph"])
    multiwoz_fallback = deterministic_top(multiwoz_global)

    total = model_hits = baseline_hits = graph_covered = 0
    scorable_user = user_hits = 0
    target_counts: Counter[str] = Counter()
    predicted_counts: Counter[str] = Counter()
    predicted_user_counts: Counter[str] = Counter()

    for source, target in pairs:
        total += 1
        target_counts[target.basic_act] += 1
        baseline_hits += int(target.basic_act == mrda_baseline_act)

        predicted_user = classifier.predict(source.text)
        predicted_user_counts[predicted_user] += 1
        expected_user = expected_multiwoz_user_act(source.basic_act)
        if expected_user is not None:
            scorable_user += 1
            user_hits += int(predicted_user == expected_user)

        predicted_system, covered = STYLE.BRIDGE.TRANSITIONS.predict_graph(
            (predicted_user,), multiwoz_edges, multiwoz_fallback
        )
        graph_covered += int(covered)
        predicted_basic = model_system_act_to_mrda_basic(predicted_system)
        predicted_counts[predicted_basic] += 1
        model_hits += int(predicted_basic == target.basic_act)

    if not total or not scorable_user:
        raise ValueError("MRDA transfer evaluation produced insufficient pairs")

    model_accuracy = model_hits / total
    baseline_accuracy = baseline_hits / total
    representable_count = sum(target_counts[label] for label in REPRESENTABLE_BASIC_RESPONSE_ACTS)
    representable_coverage = representable_count / total
    user_accuracy = user_hits / scorable_user

    return {
        "pairCount": total,
        "scorableUserActCount": scorable_user,
        "scorableUserActTop1Accuracy": user_accuracy,
        "responseTop1Accuracy": model_accuracy,
        "responseBaselineTop1Accuracy": baseline_accuracy,
        "responseAbsoluteGain": model_accuracy - baseline_accuracy,
        "multiwozGraphCoverage": graph_covered / total,
        "representableHumanResponseCoverage": representable_coverage,
        "targetBasicActCounts": dict(sorted(target_counts.items())),
        "predictedBasicActCounts": dict(sorted(predicted_counts.items())),
        "predictedUserActCounts": dict(sorted(predicted_user_counts.items())),
        "missingHumanResponseClasses": sorted(set(target_counts) - REPRESENTABLE_BASIC_RESPONSE_ACTS),
    }


def main() -> None:
    mrda_root_value = os.environ.get("MRDA_ROOT")
    if not mrda_root_value:
        raise SystemExit("MRDA_ROOT is required")
    source_sha = os.environ.get("MRDA_SHA", EXPECTED_MRDA_SHA)
    if source_sha != EXPECTED_MRDA_SHA:
        raise SystemExit(f"MRDA revision mismatch: {source_sha} != {EXPECTED_MRDA_SHA}")

    model_path_value = os.environ.get("G6_DERIVED_STYLE_MODEL_PATH")
    if not model_path_value:
        raise SystemExit("G6_DERIVED_STYLE_MODEL_PATH is required")
    model_path = Path(model_path_value)
    if not model_path.exists():
        raise SystemExit(f"derived style model does not exist: {model_path}")
    model = json.loads(model_path.read_text(encoding="utf-8"))

    mrda_root = Path(mrda_root_value)
    train_pairs = cross_speaker_pairs(load_turns(mrda_root / "train_set.txt"))
    test_pairs = cross_speaker_pairs(load_turns(mrda_root / "test_set.txt"))

    native_global, native_edges = build_native_graph(train_pairs)
    native = evaluate_native_graph(test_pairs, native_global, native_edges)
    transfer = evaluate_current_style_model(
        test_pairs,
        model,
        mrda_baseline_act=native["globalBaselinePrediction"],
    )

    transfer_pass = (
        transfer["representableHumanResponseCoverage"] >= MIN_REPRESENTABLE_TARGET_COVERAGE
        and transfer["scorableUserActTop1Accuracy"] >= MIN_SCORABLE_USER_ACT_ACCURACY
        and transfer["responseAbsoluteGain"] >= MIN_TRANSFER_GAIN
    )
    native_graph_earned = (
        native["conditionalGraphAbsoluteGain"] >= MIN_NATIVE_GRAPH_GAIN
        and native["conditionalGraphCoverage"] >= MIN_NATIVE_GRAPH_COVERAGE
    )
    semantic_evidence = (
        "MOTIVATED_BY_CROSS_DOMAIN_LEXICAL_FAILURE"
        if transfer["scorableUserActTop1Accuracy"] < MIN_SCORABLE_USER_ACT_ACCURACY
        else "NOT_EARNED_CROSS_DOMAIN_LEXICAL_BRIDGE_SUFFICIENT"
    )

    receipt = {
        "status": "PASS",
        "qualificationStatus": "PASS" if transfer_pass else "MEASURED_DOMAIN_GAP",
        "source": "ICSI-MRDA-via-NathanDuran-MRDA-Corpus",
        "sourceRevision": source_sha,
        "trainingSplit": "train_set.txt",
        "evaluationSplit": "test_set.txt",
        "sourceKind": "naturally_occurring_multi_party_human_meetings",
        "rawDialogueEmitted": False,
        "factualAuthority": False,
        "selectionPolicy": {
            "minimumRepresentableHumanResponseCoverage": MIN_REPRESENTABLE_TARGET_COVERAGE,
            "minimumScorableUserActTop1Accuracy": MIN_SCORABLE_USER_ACT_ACCURACY,
            "minimumResponseAbsoluteGain": MIN_TRANSFER_GAIN,
            "minimumNativeGraphAbsoluteGain": MIN_NATIVE_GRAPH_GAIN,
            "minimumNativeGraphCoverage": MIN_NATIVE_GRAPH_COVERAGE,
        },
        "currentModelTransfer": transfer,
        "nativeMrdaGraph": native,
        "nativeGraphEvidence": (
            "SECOND_CORPUS_GRAPH_EARNED" if native_graph_earned else "SECOND_CORPUS_GRAPH_NOT_EARNED"
        ),
        "semanticMatcherEvidence": semantic_evidence,
    }

    target_value = os.environ.get("G6_MRDA_TRANSFER_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
