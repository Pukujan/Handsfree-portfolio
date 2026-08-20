from __future__ import annotations

from collections import Counter, defaultdict
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SCRIPT = ROOT / "scripts" / "verify_g6_multiwoz_utterance_bridge.py"
MRDA_SCRIPT = ROOT / "scripts" / "verify_g6_mrda_transfer.py"

BRIDGE_SPEC = importlib.util.spec_from_file_location("g6_bridge_for_semantic", BRIDGE_SCRIPT)
assert BRIDGE_SPEC and BRIDGE_SPEC.loader
BRIDGE = importlib.util.module_from_spec(BRIDGE_SPEC)
sys.modules[BRIDGE_SPEC.name] = BRIDGE
BRIDGE_SPEC.loader.exec_module(BRIDGE)

MRDA_SPEC = importlib.util.spec_from_file_location("g6_mrda_for_semantic", MRDA_SCRIPT)
assert MRDA_SPEC and MRDA_SPEC.loader
MRDA = importlib.util.module_from_spec(MRDA_SPEC)
sys.modules[MRDA_SPEC.name] = MRDA
MRDA_SPEC.loader.exec_module(MRDA)

SEMANTIC_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
SEMANTIC_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
SENTENCE_TRANSFORMERS_VERSION = "5.6.1"
MIN_MRDA_USER_ACT_ACCURACY = 0.80
MIN_MRDA_ABSOLUTE_IMPROVEMENT = 0.20
MIN_MULTIWOZ_USER_ACT_ACCURACY = 0.80


def decide_semantic_admission(
    *,
    mrda_user_act_accuracy: float,
    lexical_mrda_user_act_accuracy: float,
    multiwoz_user_act_accuracy: float,
) -> str:
    improvement = mrda_user_act_accuracy - lexical_mrda_user_act_accuracy
    if (
        mrda_user_act_accuracy >= MIN_MRDA_USER_ACT_ACCURACY
        and improvement >= MIN_MRDA_ABSOLUTE_IMPROVEMENT
        and multiwoz_user_act_accuracy >= MIN_MULTIWOZ_USER_ACT_ACCURACY
    ):
        return "SEMANTIC_BRIDGE_EARNED_FOR_USER_ACT_CLASSIFICATION_ONLY"
    return "SEMANTIC_BRIDGE_NOT_EARNED"


def _normalize(vector, np):
    norm = float(np.linalg.norm(vector))
    return vector if norm == 0.0 else vector / norm


def build_centroids(examples, embeddings, np):
    sums = {}
    counts: Counter[str] = Counter()
    for example, embedding in zip(examples, embeddings, strict=True):
        for label in example.user_acts:
            if label not in sums:
                sums[label] = np.zeros_like(embedding)
            sums[label] += embedding
            counts[label] += 1
    if not counts:
        raise ValueError("semantic centroid training received no labels")
    classes = tuple(sorted(counts))
    centroids = np.stack([_normalize(sums[label] / counts[label], np) for label in classes])
    return classes, centroids, counts


def predict_labels(embeddings, classes: tuple[str, ...], centroids, np) -> list[str]:
    scores = embeddings @ centroids.T
    indices = np.argmax(scores, axis=1)
    return [classes[int(index)] for index in indices]


def evaluate_multiwoz(examples, predictions: Iterable[str]) -> dict:
    examples = tuple(examples)
    predictions = tuple(predictions)
    if len(examples) != len(predictions) or not examples:
        raise ValueError("MultiWOZ semantic evaluation shape mismatch")
    hits = sum(int(prediction in example.user_acts) for example, prediction in zip(examples, predictions, strict=True))
    return {"exampleCount": len(examples), "userActTop1Accuracy": hits / len(examples)}


def evaluate_mrda(pairs, predictions: Iterable[str]) -> dict:
    pairs = tuple(pairs)
    predictions = tuple(predictions)
    if len(pairs) != len(predictions):
        raise ValueError("MRDA semantic evaluation shape mismatch")
    total = hits = 0
    predicted: Counter[str] = Counter()
    for (source, _target), prediction in zip(pairs, predictions, strict=True):
        expected = MRDA.expected_multiwoz_user_act(source.basic_act)
        if expected is None:
            continue
        total += 1
        predicted[prediction] += 1
        hits += int(prediction == expected)
    if not total:
        raise ValueError("MRDA semantic evaluation has no directly comparable S/Q turns")
    return {
        "scorableUserActCount": total,
        "userActTop1Accuracy": hits / total,
        "predictedUserActCounts": dict(sorted(predicted.items())),
    }


def main() -> None:
    multiwoz_root_value = os.environ.get("MULTIWOZ_ROOT")
    mrda_root_value = os.environ.get("MRDA_ROOT")
    mrda_receipt_value = os.environ.get("G6_MRDA_TRANSFER_RECEIPT_PATH")
    if not multiwoz_root_value or not mrda_root_value or not mrda_receipt_value:
        raise SystemExit("MULTIWOZ_ROOT, MRDA_ROOT and G6_MRDA_TRANSFER_RECEIPT_PATH are required")
    if os.environ.get("MULTIWOZ_SHA", BRIDGE.EXPECTED_SOURCE_SHA) != BRIDGE.EXPECTED_SOURCE_SHA:
        raise SystemExit("MultiWOZ revision mismatch")
    if os.environ.get("MRDA_SHA", MRDA.EXPECTED_MRDA_SHA) != MRDA.EXPECTED_MRDA_SHA:
        raise SystemExit("MRDA revision mismatch")

    configured_revision = os.environ.get("G6_SEMANTIC_MODEL_REVISION", SEMANTIC_MODEL_REVISION)
    if configured_revision != SEMANTIC_MODEL_REVISION:
        raise SystemExit(f"semantic model revision mismatch: {configured_revision} != {SEMANTIC_MODEL_REVISION}")

    try:
        import numpy as np
        import sentence_transformers
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit("sentence-transformers evaluation dependency is required") from exc

    if sentence_transformers.__version__ != SENTENCE_TRANSFORMERS_VERSION:
        raise SystemExit(
            f"sentence-transformers version mismatch: {sentence_transformers.__version__} != {SENTENCE_TRANSFORMERS_VERSION}"
        )

    multiwoz_root = Path(multiwoz_root_value)
    action_data = BRIDGE.TRANSITIONS._load(multiwoz_root / "dialog_acts.json")
    train_examples = list(BRIDGE.iter_split_examples(multiwoz_root, "dev", action_data))
    test_examples = list(BRIDGE.iter_split_examples(multiwoz_root, "test", action_data))

    mrda_pairs = MRDA.cross_speaker_pairs(MRDA.load_turns(Path(mrda_root_value) / "test_set.txt"))
    mrda_source_texts = [source.text for source, _target in mrda_pairs]

    model = SentenceTransformer(
        SEMANTIC_MODEL_ID,
        revision=SEMANTIC_MODEL_REVISION,
        trust_remote_code=False,
    )
    train_embeddings = model.encode(
        [example.text for example in train_examples],
        batch_size=128,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    classes, centroids, class_counts = build_centroids(train_examples, train_embeddings, np)

    multiwoz_embeddings = model.encode(
        [example.text for example in test_examples],
        batch_size=128,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    multiwoz_predictions = predict_labels(multiwoz_embeddings, classes, centroids, np)
    multiwoz_result = evaluate_multiwoz(test_examples, multiwoz_predictions)

    mrda_embeddings = model.encode(
        mrda_source_texts,
        batch_size=128,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    mrda_predictions = predict_labels(mrda_embeddings, classes, centroids, np)
    mrda_result = evaluate_mrda(mrda_pairs, mrda_predictions)

    mrda_receipt = json.loads(Path(mrda_receipt_value).read_text(encoding="utf-8"))
    lexical_accuracy = float(mrda_receipt["currentModelTransfer"]["scorableUserActTop1Accuracy"])
    improvement = mrda_result["userActTop1Accuracy"] - lexical_accuracy
    admission = decide_semantic_admission(
        mrda_user_act_accuracy=mrda_result["userActTop1Accuracy"],
        lexical_mrda_user_act_accuracy=lexical_accuracy,
        multiwoz_user_act_accuracy=multiwoz_result["userActTop1Accuracy"],
    )

    receipt = {
        "status": "PASS",
        "experimentKind": "evaluation_only_semantic_user_act_bridge",
        "modelId": SEMANTIC_MODEL_ID,
        "modelRevision": SEMANTIC_MODEL_REVISION,
        "modelLicense": "Apache-2.0",
        "sentenceTransformersVersion": SENTENCE_TRANSFORMERS_VERSION,
        "trainingSource": "MultiWOZ-2.2-dev",
        "evaluationSources": ["MultiWOZ-2.2-test", "MRDA-test"],
        "classifier": "nearest_normalized_class_centroid",
        "trainingClassCounts": dict(sorted(class_counts.items())),
        "multiwoz": multiwoz_result,
        "mrda": mrda_result,
        "lexicalMrdaUserActTop1Accuracy": lexical_accuracy,
        "mrdaAbsoluteImprovementOverLexical": improvement,
        "selectionPolicy": {
            "minimumMrdaUserActTop1Accuracy": MIN_MRDA_USER_ACT_ACCURACY,
            "minimumMrdaAbsoluteImprovementOverLexical": MIN_MRDA_ABSOLUTE_IMPROVEMENT,
            "minimumMultiwozUserActTop1Accuracy": MIN_MULTIWOZ_USER_ACT_ACCURACY,
        },
        "semanticRuntimeAdmission": admission,
        "responseGraphAdmission": "NOT_EVALUATED_BY_SEMANTIC_EXPERIMENT",
        "rawDialogueEmitted": False,
        "factualAuthority": False,
    }

    target_value = os.environ.get("G6_SEMANTIC_TRANSFER_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
