from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json

MATCH_WEIGHTS = {
    "context_dependency": 8,
    "user_register": 4,
    "urgency": 3,
    "previous_act": 2,
}

FORBIDDEN_PATTERN_KEYS = {
    "answer",
    "answerText",
    "claim",
    "claims",
    "evidence",
    "evidenceRefs",
    "facts",
    "proposition",
    "question",
    "responseText",
    "sourceText",
    "utterance",
}


@dataclass(frozen=True)
class InteractionSituation:
    situation_id: str
    user_act: str
    context_dependency: str
    user_register: str
    urgency: str = "normal"
    previous_act: str | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "InteractionSituation":
        return cls(
            situation_id=str(payload["situationId"]),
            user_act=str(payload["userAct"]),
            context_dependency=str(payload["contextDependency"]),
            user_register=str(payload["userRegister"]),
            urgency=str(payload.get("urgency", "normal")),
            previous_act=payload.get("previousAct"),
        )


@dataclass(frozen=True)
class ResponsePattern:
    pattern_id: str
    user_act: str
    context_dependency: str | None
    user_register: str | None
    urgency: str | None
    previous_act: str | None
    response_moves: tuple[str, ...]
    length_band: str
    acknowledge_previous: bool
    repeat_question: bool
    unsolicited_offer: bool
    research_refs: tuple[str, ...]

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ResponsePattern":
        match = payload["match"]
        strategy = payload["strategy"]
        return cls(
            pattern_id=str(payload["patternId"]),
            user_act=str(match["userAct"]),
            context_dependency=match.get("contextDependency"),
            user_register=match.get("userRegister"),
            urgency=match.get("urgency"),
            previous_act=match.get("previousAct"),
            response_moves=tuple(str(value) for value in strategy["moves"]),
            length_band=str(strategy["lengthBand"]),
            acknowledge_previous=bool(strategy["acknowledgePrevious"]),
            repeat_question=bool(strategy["repeatQuestion"]),
            unsolicited_offer=bool(strategy["unsolicitedOffer"]),
            research_refs=tuple(str(value) for value in payload["researchRefs"]),
        )


@dataclass(frozen=True)
class MatchResult:
    pattern: ResponsePattern
    score: int
    matched_dimensions: tuple[str, ...]


def _reject_factual_payload(value: Any, *, path: str = "pattern") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PATTERN_KEYS:
                raise ValueError(f"{path} contains forbidden factual/text field: {key}")
            _reject_factual_payload(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_factual_payload(child, path=f"{path}[{index}]")


def load_pattern_catalog(path: Path) -> tuple[ResponsePattern, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("authority") != "style_only":
        raise ValueError("dialogue pattern catalog must declare authority=style_only")
    patterns = payload.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("dialogue pattern catalog must contain at least one pattern")

    parsed: list[ResponsePattern] = []
    seen: set[str] = set()
    for raw in patterns:
        _reject_factual_payload(raw)
        pattern = ResponsePattern.from_mapping(raw)
        if pattern.pattern_id in seen:
            raise ValueError(f"duplicate dialogue pattern id: {pattern.pattern_id}")
        if not pattern.research_refs:
            raise ValueError(f"dialogue pattern lacks research provenance: {pattern.pattern_id}")
        seen.add(pattern.pattern_id)
        parsed.append(pattern)
    return tuple(parsed)


def score_pattern(pattern: ResponsePattern, situation: InteractionSituation) -> MatchResult | None:
    if pattern.user_act not in {situation.user_act, "*"}:
        return None

    score = 100 if pattern.user_act == situation.user_act else 0
    matched: list[str] = ["user_act"] if pattern.user_act == situation.user_act else []

    for field, weight in MATCH_WEIGHTS.items():
        expected = getattr(pattern, field)
        if expected is None or expected == "*":
            continue
        actual = getattr(situation, field)
        if expected == actual:
            score += weight
            matched.append(field)
        else:
            score -= weight

    return MatchResult(pattern=pattern, score=score, matched_dimensions=tuple(matched))


class DeterministicPatternMatcher:
    def __init__(self, patterns: Iterable[ResponsePattern]) -> None:
        self._patterns = tuple(patterns)
        if not self._patterns:
            raise ValueError("at least one dialogue pattern is required")

    def rank(self, situation: InteractionSituation) -> tuple[MatchResult, ...]:
        scored = [
            result
            for pattern in self._patterns
            if (result := score_pattern(pattern, situation)) is not None
        ]
        if not scored:
            raise LookupError(f"no dialogue pattern matched user act {situation.user_act!r}")
        return tuple(sorted(scored, key=lambda item: (-item.score, item.pattern.pattern_id)))

    def match(self, situation: InteractionSituation) -> MatchResult:
        return self.rank(situation)[0]


__all__ = [
    "DeterministicPatternMatcher",
    "InteractionSituation",
    "MatchResult",
    "ResponsePattern",
    "load_pattern_catalog",
    "score_pattern",
]
