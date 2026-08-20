from __future__ import annotations

from collections import Counter
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
from typing import Iterable

from handsfree_portfolio.adapters.clock import SystemClock
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy
from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions
from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.application.grounded_rendering import ClaimBoundTemplateRenderer, DeterministicGroundingVerifier
from handsfree_portfolio.application.retrieval import PublicClaimRetriever

ROOT = Path(__file__).resolve().parents[1]
SIMULATOR_SCRIPT = ROOT / "scripts" / "run_g6_simulator.py"
MULTIWOZ_SCRIPT = ROOT / "scripts" / "verify_g6_multiwoz_transitions.py"
MRDA_SCRIPT = ROOT / "scripts" / "verify_g6_mrda_transfer.py"
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
PERSONAS = ROOT / "assurance" / "personas" / "personas-v1.json"
POLICY = KNOWLEDGE / "retrieval-v1.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SIMULATOR = _load_module("g6_simulator_for_surface", SIMULATOR_SCRIPT)
MULTIWOZ = _load_module("g6_multiwoz_for_surface", MULTIWOZ_SCRIPT)
MRDA = _load_module("g6_mrda_for_surface", MRDA_SCRIPT)

ASSISTANTESE_PREFIXES = (
    "absolutely",
    "certainly",
    "of course",
    "great question",
    "good question",
    "i'd be happy",
    "i would be happy",
    "sure!",
)
UNSOLICITED_CLOSING_MARKERS = (
    "would you like me to",
    "want me to",
    "let me know if",
    "feel free to ask",
    "happy to elaborate",
    "happy to explain",
)
ACK_PREFIX_TOKENS = {
    "yeah", "yes", "yep", "no", "nope", "okay", "ok", "right", "well", "sure", "exactly",
}
EXPLICIT_PREMISE_MARKERS = (
    "i thought",
    "you said",
    "but you",
    "isn't",
    "isnt",
    "aren't",
    "arent",
    "doesn't that mean",
    "doesnt that mean",
    "so you're",
    "so you are",
    "actually",
)
MIN_HUMAN_REFERENCE_PAIRS = 100
MAX_ASSISTANTESE_RATE = 0.0
MAX_UNSOLICITED_CLOSING_RATE = 0.0
MAX_HEADING_OR_LIST_RATE = 0.0
MAX_MISAPPLIED_CORRECTION_RATE = 0.0


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text)


def word_count(text: str) -> int:
    return len(words(text))


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires values")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be in [0, 1]")
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return float(ordered[index])


def starts_with_assistantese(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(prefix) for prefix in ASSISTANTESE_PREFIXES)


def has_unsolicited_closing(text: str) -> bool:
    lowered = text.strip().lower()
    return any(marker in lowered for marker in UNSOLICITED_CLOSING_MARKERS)


def has_heading_or_list(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return any(
        line.startswith(("#", "- ", "* ")) or re.match(r"^\d+[.)]\s+", line) is not None
        for line in lines
    )


def acknowledgement_prefix(text: str) -> bool:
    tokens = [token.lower() for token in words(text)]
    return bool(tokens and tokens[0] in ACK_PREFIX_TOKENS)


def explicit_premise_challenge(question: str) -> bool:
    lowered = question.strip().lower()
    return any(marker in lowered for marker in EXPLICIT_PREMISE_MARKERS)


def misapplied_correction(question: str, answer: str) -> bool:
    return answer.strip().lower().startswith("not quite.") and not explicit_premise_challenge(question)


def derive_ratio_question_floor(
    multiwoz_pairs: Iterable[tuple[str, str]],
    mrda_pairs: Iterable[tuple[str, str]],
) -> int:
    """Stabilize response/question ratios for terse prompts using human data only.

    Ratios become numerically unstable when the denominator is a one-to-three-word
    stress prompt. The floor is therefore derived from the smaller median human
    question length across the two reference corpora; production data never tunes it.
    """
    multiwoz_questions = [word_count(question) for question, _answer in multiwoz_pairs]
    mrda_questions = [word_count(question) for question, _answer in mrda_pairs]
    if not multiwoz_questions or not mrda_questions:
        raise ValueError("ratio floor requires both human reference corpora")
    return max(
        1,
        math.floor(min(statistics.median(multiwoz_questions), statistics.median(mrda_questions))),
    )


def surface_stats(pairs: Iterable[tuple[str, str]], *, ratio_question_floor: int = 1) -> dict:
    pairs = tuple(pairs)
    if not pairs:
        raise ValueError("surface stats require pairs")
    if ratio_question_floor < 1:
        raise ValueError("ratio_question_floor must be positive")
    question_words = [word_count(question) for question, _answer in pairs]
    response_words = [word_count(answer) for _question, answer in pairs]
    raw_ratios = [
        word_count(answer) / max(word_count(question), 1)
        for question, answer in pairs
    ]
    floor_normalized_ratios = [
        word_count(answer) / max(word_count(question), ratio_question_floor)
        for question, answer in pairs
    ]
    count = len(pairs)
    return {
        "pairCount": count,
        "medianQuestionWords": statistics.median(question_words),
        "p10QuestionWords": percentile(question_words, 0.10),
        "medianResponseWords": statistics.median(response_words),
        "p90ResponseWords": percentile(response_words, 0.90),
        "p95ResponseWords": percentile(response_words, 0.95),
        "medianResponseToQuestionWordRatio": statistics.median(raw_ratios),
        "p90ResponseToQuestionWordRatio": percentile(raw_ratios, 0.90),
        "ratioQuestionFloorWords": ratio_question_floor,
        "medianFloorNormalizedResponseToQuestionWordRatio": statistics.median(floor_normalized_ratios),
        "p90FloorNormalizedResponseToQuestionWordRatio": percentile(floor_normalized_ratios, 0.90),
        "acknowledgementPrefixRate": sum(acknowledgement_prefix(answer) for _q, answer in pairs) / count,
        "assistantesePrefixRate": sum(starts_with_assistantese(answer) for _q, answer in pairs) / count,
        "unsolicitedClosingRate": sum(has_unsolicited_closing(answer) for _q, answer in pairs) / count,
        "headingOrListRate": sum(has_heading_or_list(answer) for _q, answer in pairs) / count,
        "misappliedCorrectionRate": sum(misapplied_correction(question, answer) for question, answer in pairs) / count,
    }


def iter_multiwoz_request_response_text(root: Path, action_data: dict):
    for path in sorted((root / "test").glob("dialogues_*.json")):
        dialogues = MULTIWOZ._load(path)
        for dialogue in dialogues:
            dialogue_id = str(dialogue["dialogue_id"])
            turns = dialogue.get("turns", [])
            for index in range(0, len(turns) - 1, 2):
                user = turns[index]
                system = turns[index + 1]
                if user.get("speaker") != "USER" or system.get("speaker") != "SYSTEM":
                    continue
                user_acts = MULTIWOZ._acts_for_turn(action_data, dialogue_id, index)
                system_acts = MULTIWOZ._acts_for_turn(action_data, dialogue_id, index + 1)
                if "request" not in user_acts or "inform" not in system_acts:
                    continue
                question = str(user.get("utterance", "")).strip()
                answer = str(system.get("utterance", "")).strip()
                if question and answer:
                    yield question, answer


def iter_mrda_question_content_pairs(root: Path):
    for source, target in MRDA.cross_speaker_pairs(MRDA.load_turns(root / "test_set.txt")):
        if source.basic_act == "Q" and target.basic_act == "S" and source.text.strip() and target.text.strip():
            yield source.text.strip(), target.text.strip()


def production_pairs() -> tuple[tuple[str, str], ...]:
    personas = json.loads(PERSONAS.read_text(encoding="utf-8"))["personas"]
    catalog = SIMULATOR.FixtureCatalog()
    pairs: list[tuple[str, str]] = []
    for persona in personas:
        sessions = InMemoryConversationSessions()
        kernel = ConversationKernel(
            catalog=catalog,
            retriever=PublicClaimRetriever(catalog, load_retrieval_policy(POLICY)),
            sessions=sessions,
            renderer=ClaimBoundTemplateRenderer(),
            verifier=DeterministicGroundingVerifier(),
            clock=SystemClock(),
        )
        for question in SIMULATOR.workload(persona):
            events = list(kernel.stream_turn(conversation_id=persona["id"], question=question))
            delta = SIMULATOR.event(events, "answer.delta")
            if delta is None or not delta.payload.get("claimIds"):
                continue
            pairs.append((question, str(delta.payload.get("text", ""))))
    if not pairs:
        raise ValueError("production workload produced no supported answers")
    return tuple(pairs)


def evaluate_surface_envelope(production: dict, multiwoz: dict, mrda: dict) -> tuple[str, list[str], dict]:
    if multiwoz["pairCount"] < MIN_HUMAN_REFERENCE_PAIRS or mrda["pairCount"] < MIN_HUMAN_REFERENCE_PAIRS:
        raise ValueError("human surface reference sample is unexpectedly small")
    floors = {
        production["ratioQuestionFloorWords"],
        multiwoz["ratioQuestionFloorWords"],
        mrda["ratioQuestionFloorWords"],
    }
    if len(floors) != 1:
        raise ValueError("surface comparisons must use one human-derived ratio question floor")

    human_p95_words = max(multiwoz["p95ResponseWords"], mrda["p95ResponseWords"])
    human_p90_floor_ratio = max(
        multiwoz["p90FloorNormalizedResponseToQuestionWordRatio"],
        mrda["p90FloorNormalizedResponseToQuestionWordRatio"],
    )
    defects: list[str] = []
    if production["medianResponseWords"] > human_p95_words:
        defects.append("MEDIAN_RESPONSE_OVER_HUMAN_P95")
    if production["p90FloorNormalizedResponseToQuestionWordRatio"] > human_p90_floor_ratio:
        defects.append("FLOOR_NORMALIZED_RESPONSE_TO_QUESTION_RATIO_ABOVE_HUMAN_P90")
    if production["assistantesePrefixRate"] > MAX_ASSISTANTESE_RATE:
        defects.append("ASSISTANTESE_PREFIX")
    if production["unsolicitedClosingRate"] > MAX_UNSOLICITED_CLOSING_RATE:
        defects.append("UNSOLICITED_CLOSING")
    if production["headingOrListRate"] > MAX_HEADING_OR_LIST_RATE:
        defects.append("HEADING_OR_LIST")
    if production["misappliedCorrectionRate"] > MAX_MISAPPLIED_CORRECTION_RATE:
        defects.append("MISAPPLIED_CORRECTION_FRAMING")

    envelope = {
        "ratioQuestionFloorWords": next(iter(floors)),
        "maximumMedianResponseWords": human_p95_words,
        "maximumP90FloorNormalizedResponseToQuestionWordRatio": human_p90_floor_ratio,
        "rawP90ResponseToQuestionWordRatioDiagnosticOnly": True,
        "maximumAssistantesePrefixRate": MAX_ASSISTANTESE_RATE,
        "maximumUnsolicitedClosingRate": MAX_UNSOLICITED_CLOSING_RATE,
        "maximumHeadingOrListRate": MAX_HEADING_OR_LIST_RATE,
        "maximumMisappliedCorrectionRate": MAX_MISAPPLIED_CORRECTION_RATE,
    }
    return ("PASS" if not defects else "MEASURED_SURFACE_DEFECT"), defects, envelope


def main() -> None:
    multiwoz_root_value = os.environ.get("MULTIWOZ_ROOT")
    mrda_root_value = os.environ.get("MRDA_ROOT")
    if not multiwoz_root_value or not mrda_root_value:
        raise SystemExit("MULTIWOZ_ROOT and MRDA_ROOT are required")
    if os.environ.get("MULTIWOZ_SHA", MULTIWOZ.EXPECTED_SOURCE_SHA) != MULTIWOZ.EXPECTED_SOURCE_SHA:
        raise SystemExit("MultiWOZ revision mismatch")
    if os.environ.get("MRDA_SHA", MRDA.EXPECTED_MRDA_SHA) != MRDA.EXPECTED_MRDA_SHA:
        raise SystemExit("MRDA revision mismatch")

    multiwoz_root = Path(multiwoz_root_value)
    action_data = MULTIWOZ._load(multiwoz_root / "dialog_acts.json")
    multiwoz_pairs = tuple(iter_multiwoz_request_response_text(multiwoz_root, action_data))
    mrda_pairs = tuple(iter_mrda_question_content_pairs(Path(mrda_root_value)))
    prod_pairs = production_pairs()
    ratio_question_floor = derive_ratio_question_floor(multiwoz_pairs, mrda_pairs)
    multiwoz_stats = surface_stats(multiwoz_pairs, ratio_question_floor=ratio_question_floor)
    mrda_stats = surface_stats(mrda_pairs, ratio_question_floor=ratio_question_floor)
    production_stats = surface_stats(prod_pairs, ratio_question_floor=ratio_question_floor)
    qualification, defects, envelope = evaluate_surface_envelope(production_stats, multiwoz_stats, mrda_stats)

    receipt = {
        "status": "PASS",
        "qualificationStatus": qualification,
        "experimentKind": "human_question_response_surface_envelope",
        "metricRevision": "short_question_floor_v2",
        "metricRationale": "Raw response/question ratios are diagnostic only for very terse prompts; the gating ratio uses a denominator floor derived solely from the smaller median human question length across the two reference corpora.",
        "sourceRevisions": {
            "multiwoz": MULTIWOZ.EXPECTED_SOURCE_SHA,
            "mrda": MRDA.EXPECTED_MRDA_SHA,
        },
        "humanReference": {
            "multiwozRequestInform": multiwoz_stats,
            "mrdaQuestionStatement": mrda_stats,
        },
        "productionSurface": production_stats,
        "surfaceEnvelope": envelope,
        "measuredDefects": defects,
        "rawDialogueEmitted": False,
        "factualAuthority": False,
        "rendererModified": False,
        "planningModified": True,
    }

    target_value = os.environ.get("G6_SURFACE_ENVELOPE_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
