from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
ASSURANCE = ROOT / "assurance"

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


def checked_out_revision() -> str | None:
    return os.environ.get("G6_CHECKED_OUT_REVISION") or os.environ.get("GITHUB_SHA")


def validate_optional_human_result() -> tuple[str, dict | None]:
    """Legacy helper retained only so historical G6 receipts/tests remain reproducible.

    Human ratings are no longer the G6 naturalness release authority. New G6
    qualification uses the corpus-backed dialogue baseline/holdout protocol.
    """
    value = os.environ.get("G6_HUMAN_RESULT_PATH")
    if not value:
        return "REQUIRED", None
    path = Path(value)
    if not path.exists():
        raise SystemExit(f"G6_HUMAN_RESULT_PATH does not exist: {path}")
    schema = load(ASSURANCE / "human" / "human-result.schema.json")
    result = load(path)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result)

    preference_total = result["candidatePreferred"] + result["baselinePreferred"] + result["ties"]
    if preference_total != result["pairedRatings"]:
        raise SystemExit(
            "human result preference counts must sum to pairedRatings: "
            f"{preference_total} != {result['pairedRatings']}"
        )

    expected_candidate = os.environ.get("G6_CANDIDATE_REVISION")
    if expected_candidate and result["candidateRevision"] != expected_candidate:
        raise SystemExit(
            "human result candidateRevision does not match frozen qualification revision: "
            f"{result['candidateRevision']} != {expected_candidate}"
        )

    blinding = result["blinding"]
    blinded = blinding["anonymizedConditionLabels"] and blinding["randomizedPairOrder"]
    sample_complete = result["raterCount"] >= 5 and result["pairedRatings"] >= 20
    preference_tied = result["candidatePreferred"] == result["baselinePreferred"]

    if not sample_complete or preference_tied or not blinded:
        expected = "INCONCLUSIVE"
    else:
        qualifies = (
            result["candidatePreferred"] > result["baselinePreferred"]
            and result["medianNaturalnessCandidate"] >= result["medianNaturalnessBaseline"]
            and result["medianAnnoyanceCandidate"] <= result["medianAnnoyanceBaseline"]
            and result["criticalIncidents"] == 0
            and result["systematicCriticalFailures"] == 0
        )
        expected = "PASS" if qualifies else "FAIL"

    if result["decision"] != expected:
        raise SystemExit(
            f"human result decision {result['decision']} conflicts with protocol-derived {expected}"
        )
    return result["decision"], result


def validate_dialogue_baseline_receipt() -> tuple[str, dict | None]:
    value = os.environ.get("G6_DIALOGUE_BASELINE_RECEIPT_PATH")
    if not value:
        return "REQUIRED", None
    path = Path(value)
    if not path.exists():
        raise SystemExit(f"G6_DIALOGUE_BASELINE_RECEIPT_PATH does not exist: {path}")
    receipt = load(path)

    required = {
        "baselineStatus": "DETERMINISTIC_BASELINE_ESTABLISHED",
        "benchmarkStatus": "DEVELOPMENT_ONLY_NOT_FINAL_HOLDOUT",
        "factualAuthority": False,
        "rawDialogueCommitted": False,
        "semanticMatcherAdmission": "NOT_EVALUATED",
        "graphMatcherAdmission": "NOT_EVALUATED",
    }
    for key, expected in required.items():
        if receipt.get(key) != expected:
            raise SystemExit(
                f"dialogue baseline receipt {key} mismatch: {receipt.get(key)!r} != {expected!r}"
            )

    for metric in (
        "top1ExactPatternAccuracy",
        "requiredMoveCoverage",
        "assistantesePolicyPassRate",
    ):
        if receipt.get(metric) != 1.0:
            raise SystemExit(f"dialogue deterministic baseline contract is not fully green: {metric}")

    return "BASELINE_ESTABLISHED", receipt


def main() -> None:
    properties_doc = load(ASSURANCE / "catalog" / "properties-v1.json")
    personas_doc = load(ASSURANCE / "personas" / "personas-v1.json")
    scenarios_doc = load(ASSURANCE / "scenarios" / "recruiter-journeys-v1.json")
    adversarial_doc = load(ASSURANCE / "adversarial" / "adversarial-v1.json")
    mutation_doc = load(ASSURANCE / "mutations" / "critical-mutations-v1.json")
    naturalness_policy = load(ASSURANCE / "catalog" / "naturalness-policy-v2.json")

    properties = properties_doc["properties"]
    if len(properties) < 13:
        raise SystemExit("G6 property catalog is incomplete")
    if any(not item.get("oracle") or not item.get("testPaths") for item in properties):
        raise SystemExit("every G6 property requires a named oracle and test path")
    declared_mutants = {item["id"] for item in mutation_doc["mutations"]}
    if declared_mutants != CRITICAL_MUTATIONS:
        raise SystemExit(f"critical mutation manifest mismatch: {sorted(declared_mutants ^ CRITICAL_MUTATIONS)}")
    if len(personas_doc["personas"]) < 9:
        raise SystemExit("G6 persona workload is incomplete")
    if len(scenarios_doc["scenarios"]) < 6 or any(not item.get("oracleRefs") for item in scenarios_doc["scenarios"]):
        raise SystemExit("G6 BDD journeys require executable oracle references")
    if len(adversarial_doc["cases"]) < 9:
        raise SystemExit("G6 adversarial corpus is incomplete")

    oracle_policy = naturalness_policy.get("oraclePolicy", {})
    if oracle_policy.get("naturalnessFinalAuthority") != "corpus_derived_deterministic_oracles":
        raise SystemExit("G6 naturalness authority must be corpus-derived deterministic oracles")
    if oracle_policy.get("modelJudges") != "auxiliary_only":
        raise SystemExit("model judges cannot become G6 naturalness authority")
    if oracle_policy.get("styleFactualAuthority") is not False:
        raise SystemExit("style retrieval cannot gain factual authority")
    naturalness_properties = naturalness_policy.get("properties", [])
    if len(naturalness_properties) < 6 or any(not item.get("oracle") or not item.get("testPaths") for item in naturalness_properties):
        raise SystemExit("G6 corpus-naturalness property catalog is incomplete")

    for schema_path in (
        ASSURANCE / "holdouts" / "holdout-manifest.schema.json",
        ASSURANCE / "conversation" / "corpus-manifest.schema.json",
    ):
        Draft202012Validator.check_schema(load(schema_path))

    private_root = ASSURANCE / "holdouts" / "private"
    if private_root.exists() and any(path.is_file() for path in private_root.rglob("*")):
        raise SystemExit("hidden holdout answers must not be committed to the public repository")

    dialogue_status, dialogue_receipt = validate_dialogue_baseline_receipt()
    receipt = {
        "machineStatus": "MACHINE_ASSURANCE_PASS",
        "naturalnessQualification": dialogue_status,
        "overallGateStatus": "CORPUS_NATURALNESS_QUALIFICATION_REQUIRED",
        "propertyCount": len(properties),
        "naturalnessPropertyCount": len(naturalness_properties),
        "criticalMutationCount": len(declared_mutants),
        "personaCount": len(personas_doc["personas"]),
        "bddScenarioCount": len(scenarios_doc["scenarios"]),
        "adversarialCaseCount": len(adversarial_doc["cases"]),
        "hiddenAnswersCommitted": False,
        "modelJudgeAuthority": "auxiliary_only",
        "naturalnessEvidenceAuthority": "public_human_dialogue_corpora_and_peer_reviewed_research",
        "factualAuthorityForStyleRetrieval": False,
        "workflowSha": checked_out_revision(),
    }
    if dialogue_receipt is not None:
        receipt["dialogueBaselineSummary"] = {
            key: dialogue_receipt[key]
            for key in (
                "baselineStatus",
                "benchmarkStatus",
                "benchmarkCaseCount",
                "patternCount",
                "researchSourceCount",
                "top1ExactPatternAccuracy",
                "requiredMoveCoverage",
                "assistantesePolicyPassRate",
                "semanticMatcherAdmission",
                "graphMatcherAdmission",
            )
        }

    target_value = os.environ.get("G6_MACHINE_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
