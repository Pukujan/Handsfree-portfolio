from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from handsfree_portfolio.domain.dialogue_behavior import DeterministicPatternMatcher, InteractionSituation, load_pattern_catalog

ROOT = Path(__file__).resolve().parents[1]
CONVERSATION = ROOT / "assurance" / "conversation"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_manifest() -> dict:
    schema = load(CONVERSATION / "corpus-manifest.schema.json")
    manifest = load(CONVERSATION / "corpus-manifest-v1.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(manifest)
    source_ids = [item["id"] for item in manifest["sources"]]
    if len(source_ids) != len(set(source_ids)):
        raise SystemExit("conversation corpus manifest contains duplicate source ids")
    if any(item["license"]["rawRedistributionAllowed"] for item in manifest["sources"]):
        raise SystemExit("G6 Slice 1 must not redistribute raw external dialogue corpora")
    return manifest


def main() -> None:
    manifest = verify_manifest()
    source_ids = {item["id"] for item in manifest["sources"]}
    patterns = load_pattern_catalog(CONVERSATION / "patterns-v1.json")
    unknown_refs = {ref for pattern in patterns for ref in pattern.research_refs if ref not in source_ids}
    if unknown_refs:
        raise SystemExit(f"dialogue patterns reference unknown research sources: {sorted(unknown_refs)}")

    benchmark = load(CONVERSATION / "development-situations-v1.json")
    if benchmark.get("status") != "development_baseline":
        raise SystemExit("public dialogue benchmark must remain labeled development_baseline until holdout freeze")

    matcher = DeterministicPatternMatcher(patterns)
    exact = move_ok = assistantese_ok = 0
    results = []
    for case in benchmark["cases"]:
        result = matcher.match(InteractionSituation.from_mapping(case["input"]))
        pattern = result.pattern
        exact_match = pattern.pattern_id == case["expectedPatternId"]
        moves_match = set(case["requiredMoves"]) <= set(pattern.response_moves)
        policy_match = not pattern.repeat_question and not pattern.unsolicited_offer
        exact += int(exact_match)
        move_ok += int(moves_match)
        assistantese_ok += int(policy_match)
        results.append({"id":case["id"],"patternId":pattern.pattern_id,"score":result.score,"exact":exact_match,"requiredMovesPresent":moves_match,"assistantesePolicyPass":policy_match})

    count = len(results)
    if count < 10:
        raise SystemExit("dialogue development benchmark is too small to establish the deterministic baseline")
    if exact != count or move_ok != count or assistantese_ok != count:
        raise SystemExit(f"deterministic dialogue baseline contract failed: exact={exact}/{count}, moves={move_ok}/{count}, assistantese={assistantese_ok}/{count}")

    receipt = {
        "baselineStatus":"DETERMINISTIC_BASELINE_ESTABLISHED",
        "benchmarkStatus":"DEVELOPMENT_ONLY_NOT_FINAL_HOLDOUT",
        "benchmarkCaseCount":count,
        "patternCount":len(patterns),
        "researchSourceCount":len(source_ids),
        "top1ExactPatternAccuracy":exact/count,
        "requiredMoveCoverage":move_ok/count,
        "assistantesePolicyPassRate":assistantese_ok/count,
        "factualAuthority":False,
        "rawDialogueCommitted":False,
        "semanticMatcherAdmission":"NOT_EVALUATED",
        "graphMatcherAdmission":"NOT_EVALUATED"
    }
    target_value = os.environ.get("G6_DIALOGUE_BASELINE_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
