from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions, StaleGenerationError
from handsfree_portfolio.application.grounded_rendering import ClaimBoundTemplateRenderer, DeterministicGroundingVerifier
from handsfree_portfolio.domain.models import AnswerPlan, EvidenceRef, RenderedAnswer, SupportedClaim
from scripts.verify_g6_machine import checked_out_revision, validate_optional_human_result

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "assurance" / "catalog" / "properties-v1.json"
PERSONAS = ROOT / "assurance" / "personas" / "personas-v1.json"
SCENARIOS = ROOT / "assurance" / "scenarios" / "recruiter-journeys-v1.json"
ADVERSARIAL = ROOT / "assurance" / "adversarial" / "adversarial-v1.json"
HUMAN_RESULT_SCHEMA = ROOT / "assurance" / "human" / "human-result.schema.json"

CRITICAL_MUTATIONS = {
    "MUT-PACK-FILTER-DISABLED",
    "MUT-STALE-EVIDENCE-ACCEPTED",
    "MUT-PRIOR-CITATION-REUSED",
    "MUT-GENERATION-FENCE-SKIPPED",
    "MUT-LIFECYCLE-INVERTED",
    "MUT-CACHE-VALIDATION-BYPASSED",
    "MUT-RENDERER-EXPANSION-ALLOWED",
    "MUT-LATENCY-ALWAYS",
    "MUT-LATENCY-NEVER",
    "MUT-INTERRUPT-CONTINUES-SPEAKING",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def supported_plan(*, proposition: str = "FOSSIL keeps durable evidence canonical.") -> AnswerPlan:
    evidence = EvidenceRef("ev-1", "Pukujan/fossil-core@sha:ARCHITECTURE.md", "FOSSIL architecture")
    claim = SupportedClaim("clm-1", proposition, "supported", (evidence.evidence_id,))
    return AnswerPlan("turn-1", 1, "ANSWER_DIRECT", (claim,), (evidence,))


def human_result(**overrides: object) -> dict:
    payload = {
        "protocolVersion": "1.0.0",
        "candidateRevision": "a" * 40,
        "baselineRevision": "baseline-1",
        "holdoutBundleId": "holdout-01",
        "holdoutManifestSha256": "b" * 64,
        "blinding": {
            "anonymizedConditionLabels": True,
            "randomizedPairOrder": True,
        },
        "raterCount": 5,
        "pairedRatings": 20,
        "candidatePreferred": 12,
        "baselinePreferred": 7,
        "ties": 1,
        "medianNaturalnessCandidate": 6,
        "medianNaturalnessBaseline": 5,
        "medianAnnoyanceCandidate": 2,
        "medianAnnoyanceBaseline": 3,
        "criticalIncidents": 0,
        "systematicCriticalFailures": 0,
        "decision": "PASS",
    }
    payload.update(overrides)
    return payload


def write_human_result(tmp_path: Path, payload: dict) -> Path:
    target = tmp_path / "human-result.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_property_catalog_has_unique_named_oracles_and_critical_mutation_coverage() -> None:
    payload = load(CATALOG)
    properties = payload["properties"]
    ids = [item["id"] for item in properties]
    assert len(ids) == len(set(ids))
    assert all(item["oracle"] for item in properties)
    assert all(item["testPaths"] for item in properties)
    declared_mutations = {mutation for item in properties for mutation in item.get("mutations", [])}
    assert CRITICAL_MUTATIONS <= declared_mutations
    assert payload["oraclePolicy"]["naturalnessFinalAuthority"] == "blinded_humans"
    assert payload["oraclePolicy"]["modelJudges"] == "auxiliary_only"


def test_personas_and_bdd_scenarios_reference_known_personas() -> None:
    personas = {item["id"] for item in load(PERSONAS)["personas"]}
    scenarios = load(SCENARIOS)["scenarios"]
    assert len(personas) >= 9
    assert all(item["persona"] in personas for item in scenarios)
    assert all(item["given"] and item["turns"] and item["then"] for item in scenarios)


def test_adversarial_cases_specify_behavior_not_expected_prose() -> None:
    cases = load(ADVERSARIAL)["cases"]
    assert len(cases) >= 9
    for case in cases:
        assert case["requiredBehavior"]
        assert "expectedAnswer" not in case
        assert "expectedText" not in case


def test_no_private_holdout_answers_are_committed() -> None:
    private_root = ROOT / "assurance" / "holdouts" / "private"
    if private_root.exists():
        committed_like_files = [path for path in private_root.rglob("*") if path.is_file()]
        assert committed_like_files == []


def test_human_result_contract_requires_blinding_and_receipt_integrity() -> None:
    schema = load(HUMAN_RESULT_SCHEMA)
    required = set(schema["required"])
    assert {"holdoutManifestSha256", "blinding", "systematicCriticalFailures"} <= required
    assert schema["properties"]["blinding"]["properties"]["anonymizedConditionLabels"] == {"const": True}
    assert schema["properties"]["blinding"]["properties"]["randomizedPairOrder"] == {"const": True}


def test_receipt_revision_prefers_checked_out_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_SHA", "merge-sha")
    monkeypatch.setenv("G6_CHECKED_OUT_REVISION", "candidate-sha")
    assert checked_out_revision() == "candidate-sha"


def test_human_result_verifier_derives_protocol_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = write_human_result(tmp_path, human_result())
    monkeypatch.setenv("G6_HUMAN_RESULT_PATH", str(target))
    monkeypatch.setenv("G6_CANDIDATE_REVISION", "a" * 40)
    status, _ = validate_optional_human_result()
    assert status == "PASS"

    target.write_text(
        json.dumps(
            human_result(
                candidatePreferred=9,
                baselinePreferred=9,
                ties=2,
                decision="INCONCLUSIVE",
            )
        ),
        encoding="utf-8",
    )
    status, _ = validate_optional_human_result()
    assert status == "INCONCLUSIVE"


def test_human_result_verifier_rejects_inconsistent_preference_totals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = write_human_result(tmp_path, human_result(ties=0))
    monkeypatch.setenv("G6_HUMAN_RESULT_PATH", str(target))
    with pytest.raises(SystemExit, match="preference counts must sum to pairedRatings"):
        validate_optional_human_result()


@given(st.text(min_size=1, max_size=80).filter(lambda value: value.strip() != ""))
def test_renderer_cannot_expand_supported_plan_with_arbitrary_suffix(suffix: str) -> None:
    plan = supported_plan()
    renderer = ClaimBoundTemplateRenderer()
    verifier = DeterministicGroundingVerifier()
    good = renderer.render(plan)
    malicious = RenderedAnswer(
        turn_id=good.turn_id,
        generation=good.generation,
        text=good.text + " " + suffix,
        evidence=good.evidence,
        claim_ids=good.claim_ids,
    )
    assert verifier.verify(plan, good)
    assert not verifier.verify(plan, malicious)


@given(st.text(min_size=1, max_size=120))
def test_evidence_source_or_label_drift_is_rejected(value: str) -> None:
    plan = supported_plan()
    good = ClaimBoundTemplateRenderer().render(plan)
    verifier = DeterministicGroundingVerifier()
    drifted = EvidenceRef(
        evidence_id=good.evidence[0].evidence_id,
        source_ref=value if value != good.evidence[0].source_ref else value + "-changed",
        label=good.evidence[0].label,
    )
    candidate = RenderedAnswer(
        turn_id=good.turn_id,
        generation=good.generation,
        text=good.text,
        evidence=(drifted,),
        claim_ids=good.claim_ids,
    )
    assert not verifier.verify(plan, candidate)


@given(st.integers(min_value=1, max_value=40))
def test_conversation_generations_are_monotonic_and_old_updates_fail(count: int) -> None:
    sessions = InMemoryConversationSessions()
    generations = [sessions.begin_turn("pbt").active_generation for _ in range(count)]
    assert generations == list(range(1, count + 1))
    if count > 1:
        with pytest.raises(StaleGenerationError):
            sessions.update("pbt", generations[-2], status="complete")
    assert sessions.owns_generation("pbt", generations[-1])


@given(st.sampled_from(["proposed", "open", "disputed", "rejected", "superseded", "retracted", "stale_pending_review"]))
def test_grounding_rejects_every_non_supported_claim_state(state: str) -> None:
    evidence = EvidenceRef("ev-1", "source", "label")
    claim = SupportedClaim("clm-1", "claim", state, ("ev-1",))  # type: ignore[arg-type]
    plan = AnswerPlan("turn-1", 1, "ANSWER_DIRECT", (claim,), (evidence,))
    rendered = RenderedAnswer("turn-1", 1, "claim", (evidence,), ("clm-1",))
    assert not DeterministicGroundingVerifier().verify(plan, rendered)
