from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import statistics
from typing import Iterable

EXPECTED_SOURCE_SHA = "fe0c8e65cfcd8462bd33c86e35f21addc84ca82b"


@dataclass(frozen=True)
class TurnPair:
    user_acts: tuple[str, ...]
    system_acts: tuple[str, ...]
    user_words: int
    system_words: int


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _act_family(name: str) -> str:
    return name.rsplit("-", 1)[-1].strip().lower()


def _acts_for_turn(action_data: dict, dialogue_id: str, turn_index: int) -> tuple[str, ...]:
    turn = action_data.get(dialogue_id, {}).get(str(turn_index), {})
    acts = turn.get("dialog_act", {})
    if not isinstance(acts, dict):
        return ()
    return tuple(sorted({_act_family(name) for name in acts if str(name).strip()}))


def _word_count(text: str) -> int:
    return len([token for token in text.strip().split() if token])


def iter_split_pairs(root: Path, split: str, action_data: dict) -> Iterable[TurnPair]:
    for path in sorted((root / split).glob("dialogues_*.json")):
        dialogues = _load(path)
        for dialogue in dialogues:
            dialogue_id = str(dialogue["dialogue_id"])
            turns = dialogue.get("turns", [])
            for index in range(0, len(turns) - 1, 2):
                user = turns[index]
                system = turns[index + 1]
                if user.get("speaker") != "USER" or system.get("speaker") != "SYSTEM":
                    continue
                user_acts = _acts_for_turn(action_data, dialogue_id, index)
                system_acts = _acts_for_turn(action_data, dialogue_id, index + 1)
                if not user_acts or not system_acts:
                    continue
                yield TurnPair(
                    user_acts=user_acts,
                    system_acts=system_acts,
                    user_words=_word_count(str(user.get("utterance", ""))),
                    system_words=_word_count(str(system.get("utterance", ""))),
                )


def _top(counter: Counter[str]) -> str:
    if not counter:
        raise ValueError("cannot choose from empty counter")
    best = max(counter.values())
    return min(key for key, count in counter.items() if count == best)


def build_transition_model(pairs: Iterable[TurnPair]):
    global_system: Counter[str] = Counter()
    edges: dict[str, Counter[str]] = defaultdict(Counter)
    pair_count = 0
    for pair in pairs:
        pair_count += 1
        for system_act in pair.system_acts:
            global_system[system_act] += 1
        for user_act in pair.user_acts:
            for system_act in pair.system_acts:
                edges[user_act][system_act] += 1
    if not pair_count or not global_system:
        raise ValueError("training split produced no annotated user/system pairs")
    return global_system, edges, pair_count


def predict_graph(user_acts: tuple[str, ...], edges: dict[str, Counter[str]], fallback: str) -> tuple[str, bool]:
    combined: Counter[str] = Counter()
    for user_act in user_acts:
        combined.update(edges.get(user_act, {}))
    if not combined:
        return fallback, False
    return _top(combined), True


def evaluate(pairs: Iterable[TurnPair], global_system: Counter[str], edges: dict[str, Counter[str]]) -> dict:
    fallback = _top(global_system)
    total = baseline_hits = graph_hits = graph_covered = 0
    user_words: list[int] = []
    system_words: list[int] = []
    ratios: list[float] = []
    for pair in pairs:
        total += 1
        baseline_hits += int(fallback in pair.system_acts)
        graph_prediction, covered = predict_graph(pair.user_acts, edges, fallback)
        graph_hits += int(graph_prediction in pair.system_acts)
        graph_covered += int(covered)
        user_words.append(pair.user_words)
        system_words.append(pair.system_words)
        ratios.append(pair.system_words / max(pair.user_words, 1))
    if not total:
        raise ValueError("evaluation split produced no annotated user/system pairs")
    baseline_accuracy = baseline_hits / total
    graph_accuracy = graph_hits / total
    coverage = graph_covered / total
    return {
        "testPairCount": total,
        "globalBaselinePrediction": fallback,
        "globalBaselineTop1Accuracy": baseline_accuracy,
        "conditionalGraphTop1Accuracy": graph_accuracy,
        "conditionalGraphAbsoluteGain": graph_accuracy - baseline_accuracy,
        "conditionalGraphCoverage": coverage,
        "medianUserWords": statistics.median(user_words),
        "medianSystemWords": statistics.median(system_words),
        "medianSystemToUserWordRatio": statistics.median(ratios),
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
    license_path = root.parents[1] / "LICENSE"
    for required in (action_path, license_path, root / "dev", root / "test"):
        if not required.exists():
            raise SystemExit(f"required MultiWOZ input missing: {required}")

    action_data = _load(action_path)
    global_system, edges, train_pair_count = build_transition_model(iter_split_pairs(root, "dev", action_data))
    metrics = evaluate(iter_split_pairs(root, "test", action_data), global_system, edges)

    top_edges = []
    for user_act, counter in sorted(edges.items()):
        predicted = _top(counter)
        top_edges.append({
            "userAct": user_act,
            "predictedSystemAct": predicted,
            "support": counter[predicted],
        })

    gain = metrics["conditionalGraphAbsoluteGain"]
    coverage = metrics["conditionalGraphCoverage"]
    if gain >= 0.05 and coverage >= 0.90:
        graph_evidence = "EVIDENCE_OF_BENEFIT_NOT_RUNTIME_ADMITTED"
    else:
        graph_evidence = "NOT_EARNED"

    receipt = {
        "status": "PASS",
        "source": "MultiWOZ-2.2",
        "sourceRevision": source_sha,
        "license": "MIT",
        "licenseSha256": _sha256(license_path),
        "actionAnnotationSha256": _sha256(action_path),
        "trainingSplit": "dev",
        "evaluationSplit": "test",
        "trainingPairCount": train_pair_count,
        "userActNodeCount": len(edges),
        "topTransitionEdges": top_edges,
        "rawDialogueEmitted": False,
        "factualAuthority": False,
        "graphRuntimeAdmission": graph_evidence,
        **metrics,
    }

    target_value = os.environ.get("G6_CORPUS_TRANSITION_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
