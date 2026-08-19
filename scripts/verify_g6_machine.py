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


def validate_optional_human_result() -> tuple[str, dict | None]:
    value = os.environ.get("G6_HUMAN_RESULT_PATH")
    if not value:
        return "REQUIRED", None
    path = Path(value)
    if not path.exists():
        raise SystemExit(f"G6_HUMAN_RESULT_PATH does not exist: {path}")
    schema = load(ASSURANCE / "human" / "human-result.schema.json")
    result = load(path)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result)
    qualifies = (
        result["raterCount"] >= 5
        and result["pairedRatings"] >= 20
        and result["candidatePreferred"] > result["baselinePreferred"]
        and result["medianNaturalnessCandidate"] >= result["medianNaturalnessBaseline"]
        and result["medianAnnoyanceCandidate"] <= result["medianAnnoyanceBaseline"]
        and result["criticalIncidents"] == 0
    )
    expected = "PASS" if qualifies else "FAIL"
    if result["decision"] not in {expected, "INCONCLUSIVE"}:
        raise SystemExit(
            f"human result decision {result['decision']} conflicts with protocol-derived {expected}"
        )
    return result["decision"], result


def main() -> None:
    properties_doc = load(ASSURANCE / "catalog" / "properties-v1.json")
    personas_doc = load(ASSURANCE / "personas" / "personas-v1.json")
    scenarios_doc = load(ASSURANCE / "scenarios" / "recruiter-journeys-v1.json")
    adversarial_doc = load(ASSURANCE / "adversarial" / "adversarial-v1.json")
    mutation_doc = load(ASSURANCE / "mutations" / "critical-mutations-v1.json")

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

    for schema_path in (
        ASSURANCE / "holdouts" / "holdout-manifest.schema.json",
        ASSURANCE / "human" / "human-result.schema.json",
    ):
        Draft202012Validator.check_schema(load(schema_path))

    private_root = ASSURANCE / "holdouts" / "private"
    if private_root.exists() and any(path.is_file() for path in private_root.rglob("*")):
        raise SystemExit("hidden holdout answers must not be committed to the public repository")

    human_status, human_result = validate_optional_human_result()
    receipt = {
        "machineStatus": "MACHINE_ASSURANCE_PASS",
        "humanQualification": human_status,
        "overallGateStatus": "PASS" if human_status == "PASS" else "HUMAN_QUALIFICATION_REQUIRED",
        "propertyCount": len(properties),
        "criticalMutationCount": len(declared_mutants),
        "personaCount": len(personas_doc["personas"]),
        "bddScenarioCount": len(scenarios_doc["scenarios"]),
        "adversarialCaseCount": len(adversarial_doc["cases"]),
        "hiddenAnswersCommitted": False,
        "modelJudgeAuthority": properties_doc["oraclePolicy"]["modelJudges"],
        "naturalnessFinalAuthority": properties_doc["oraclePolicy"]["naturalnessFinalAuthority"],
        "workflowSha": os.environ.get("GITHUB_SHA"),
    }
    if human_result is not None:
        receipt["humanResultSummary"] = {
            key: human_result[key]
            for key in (
                "candidateRevision",
                "baselineRevision",
                "holdoutBundleId",
                "raterCount",
                "pairedRatings",
                "candidatePreferred",
                "baselinePreferred",
                "ties",
                "criticalIncidents",
                "decision",
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
