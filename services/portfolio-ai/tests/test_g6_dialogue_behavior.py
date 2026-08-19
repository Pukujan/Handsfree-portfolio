from __future__ import annotations

import json
from pathlib import Path

import pytest

from handsfree_portfolio.domain.dialogue_behavior import (
    DeterministicPatternMatcher,
    InteractionSituation,
    load_pattern_catalog,
)

ROOT = Path(__file__).resolve().parents[3]
CONVERSATION = ROOT / "assurance" / "conversation"
PATTERNS = CONVERSATION / "patterns-v1.json"
BENCHMARK = CONVERSATION / "development-situations-v1.json"
MANIFEST = CONVERSATION / "corpus-manifest-v1.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pattern_catalog_is_style_only_and_has_no_factual_payload() -> None:
    payload = load(PATTERNS)
    assert payload["authority"] == "style_only"
    patterns = load_pattern_catalog(PATTERNS)
    assert len(patterns) >= 8
    assert all(pattern.research_refs for pattern in patterns)
    assert all(not pattern.unsolicited_offer for pattern in patterns)
    assert all(not pattern.repeat_question for pattern in patterns)


def test_pattern_loader_rejects_factual_or_verbatim_payload(tmp_path: Path) -> None:
    payload = load(PATTERNS)
    payload["patterns"][0]["answerText"] = "forbidden"
    target = tmp_path / "bad-patterns.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden factual/text field"):
        load_pattern_catalog(target)


def test_deterministic_matcher_hits_every_public_development_case() -> None:
    matcher = DeterministicPatternMatcher(load_pattern_catalog(PATTERNS))
    for case in load(BENCHMARK)["cases"]:
        situation = InteractionSituation.from_mapping(case["input"])
        result = matcher.match(situation)
        assert result.pattern.pattern_id == case["expectedPatternId"]
        assert set(case["requiredMoves"]) <= set(result.pattern.response_moves)


def test_style_accommodation_prefers_terse_strategy_for_terse_direct_question() -> None:
    matcher = DeterministicPatternMatcher(load_pattern_catalog(PATTERNS))
    terse = InteractionSituation("terse", "direct_question", "none", "terse", "normal")
    neutral = InteractionSituation("neutral", "direct_question", "none", "neutral", "normal")
    assert matcher.match(terse).pattern.pattern_id == "PAT-DIRECT-TERSE"
    assert matcher.match(terse).pattern.length_band == "short"
    assert matcher.match(neutral).pattern.pattern_id == "PAT-DIRECT-NEUTRAL"


def test_contextual_followup_resolves_referent_before_answer() -> None:
    matcher = DeterministicPatternMatcher(load_pattern_catalog(PATTERNS))
    situation = InteractionSituation("followup", "followup_question", "high", "terse", "normal", "answer")
    assert matcher.match(situation).pattern.response_moves[:2] == ("resolve_referent", "answer")


def test_repair_and_boundary_are_explicit_conversational_moves() -> None:
    matcher = DeterministicPatternMatcher(load_pattern_catalog(PATTERNS))
    correction = InteractionSituation("correction", "correction", "high", "terse", "normal", "answer")
    private = InteractionSituation("private", "private_request", "low", "neutral")
    assert matcher.match(correction).pattern.response_moves[0] == "repair"
    assert matcher.match(private).pattern.response_moves[0] == "boundary"


def test_research_manifest_never_grants_factual_authority_or_raw_redistribution() -> None:
    manifest = load(MANIFEST)
    assert manifest["policy"]["factualAuthority"] is False
    assert manifest["policy"]["rawDialogueCommitted"] is False
    assert manifest["policy"]["modelJudgeAuthority"] == "auxiliary_only"
    assert len(manifest["sources"]) >= 5
    assert all(source["license"]["rawRedistributionAllowed"] is False for source in manifest["sources"])
