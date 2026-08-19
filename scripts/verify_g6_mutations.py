from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Mutant:
    mutation_id: str
    path: str
    old: str
    new: str
    command: tuple[str, ...]


PYTEST = (sys.executable, "-m", "pytest", "-q")
WEB_TEST = ("pnpm", "--dir", "apps/web", "exec", "vitest", "run")

MUTANTS = (
    Mutant(
        "MUT-PACK-FILTER-DISABLED",
        "services/portfolio-ai/src/handsfree_portfolio/adapters/fossil_pack.py",
        'return PackAccess(pack_id=PUBLIC_PACK_ID, read_mounts=frozenset({PUBLIC_PACK_ID}), write_targets=frozenset())',
        'return PackAccess(pack_id=PUBLIC_PACK_ID, read_mounts=frozenset({PUBLIC_PACK_ID, "pack_private_not_mounted_1234"}), write_targets=frozenset())',
        PYTEST + ("services/portfolio-ai/tests/test_fossil_pack.py::test_public_runtime_access_is_read_only_and_single_pack",),
    ),
    Mutant(
        "MUT-STALE-EVIDENCE-ACCEPTED",
        "services/portfolio-ai/src/handsfree_portfolio/application/response_cache.py",
        "            if current_evidence_ids != artifact.evidence_ids:\n                self._reject(key)\n                return None",
        "            if False and current_evidence_ids != artifact.evidence_ids:\n                self._reject(key)\n                return None",
        PYTEST + ("services/portfolio-ai/tests/test_response_cache.py::test_current_evidence_drift_rejects_cached_artifact",),
    ),
    Mutant(
        "MUT-PRIOR-CITATION-REUSED",
        "services/portfolio-ai/src/handsfree_portfolio/application/grounded_rendering.py",
        "        plan_evidence = tuple((item.evidence_id, item.source_ref, item.label) for item in plan.evidence)\n        rendered_evidence = tuple((item.evidence_id, item.source_ref, item.label) for item in rendered.evidence)",
        "        plan_evidence = tuple(item.evidence_id for item in plan.evidence)\n        rendered_evidence = tuple(item.evidence_id for item in rendered.evidence)",
        PYTEST + ("services/portfolio-ai/tests/test_g6_assurance.py::test_evidence_source_or_label_drift_is_rejected",),
    ),
    Mutant(
        "MUT-GENERATION-FENCE-SKIPPED",
        "services/portfolio-ai/src/handsfree_portfolio/adapters/session_memory.py",
        "            return self.get(conversation_id).active_generation == generation",
        "            return True",
        PYTEST + ("services/portfolio-ai/tests/test_conversation_kernel.py::test_new_generation_fences_old_turn_after_blocked_retrieval",),
    ),
    Mutant(
        "MUT-LIFECYCLE-INVERTED",
        "services/portfolio-ai/src/handsfree_portfolio/adapters/fossil_claim_catalog.py",
        '            if state.claims[claim_id] != "supported":',
        '            if state.claims[claim_id] == "supported":',
        PYTEST + ("services/portfolio-ai/tests/test_fossil_pack.py::test_reviewed_claim_preserves_source_and_requires_explicit_lifecycle_transition",),
    ),
    Mutant(
        "MUT-CACHE-VALIDATION-BYPASSED",
        "services/portfolio-ai/src/handsfree_portfolio/application/response_cache.py",
        "            if not self.verifier.verify(plan, rendered):",
        "            if False and not self.verifier.verify(plan, rendered):",
        PYTEST + ("services/portfolio-ai/tests/test_response_cache.py::test_forged_cached_text_is_rejected_by_grounding_verifier",),
    ),
    Mutant(
        "MUT-RENDERER-EXPANSION-ALLOWED",
        "services/portfolio-ai/src/handsfree_portfolio/application/grounded_rendering.py",
        "        if rendered.text != canonical_render_text(plan):",
        "        if False and rendered.text != canonical_render_text(plan):",
        PYTEST + ("services/portfolio-ai/tests/test_conversation_kernel.py::test_renderer_fact_expansion_fails_before_answer_delta",),
    ),
    Mutant(
        "MUT-LATENCY-ALWAYS",
        "apps/web/src/application/latencyBridge.ts",
        "  if (!workPending || elapsedMs < thresholdMs) return null;",
        "  if (false) return null;",
        WEB_TEST + ("src/application/latencyBridge.test.ts",),
    ),
    Mutant(
        "MUT-LATENCY-NEVER",
        "apps/web/src/application/latencyBridge.ts",
        "  return 'Yeah — lemme check the public evidence.';",
        "  return null;",
        WEB_TEST + ("src/application/latencyBridge.test.ts",),
    ),
    Mutant(
        "MUT-INTERRUPT-CONTINUES-SPEAKING",
        "apps/web/src/application/HandsFreeController.ts",
        "    this.requestAbort?.abort();\n    this.requestAbort = null;\n    this.stopSpeech();\n    this.patch({ state: 'interrupted', statusLine: 'Interrupted. Listening for your next question.' });",
        "    this.requestAbort?.abort();\n    this.requestAbort = null;\n    this.patch({ state: 'interrupted', statusLine: 'Interrupted. Listening for your next question.' });",
        WEB_TEST + ("src/application/HandsFreeController.test.ts", "-t", "interrupt stops speech and starts listening for the replacement question"),
    ),
)


def run_mutant(mutant: Mutant) -> dict:
    path = ROOT / mutant.path
    original = path.read_text(encoding="utf-8")
    count = original.count(mutant.old)
    if count != 1:
        raise RuntimeError(f"{mutant.mutation_id}: expected one mutation target, found {count}")
    mutated = original.replace(mutant.old, mutant.new, 1)
    path.write_text(mutated, encoding="utf-8")
    try:
        completed = subprocess.run(
            mutant.command,
            cwd=ROOT,
            env=os.environ.copy(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
    finally:
        path.write_text(original, encoding="utf-8")

    killed = completed.returncode != 0
    tail = "\n".join(completed.stdout.splitlines()[-12:])
    return {
        "mutationId": mutant.mutation_id,
        "target": mutant.path,
        "command": list(mutant.command),
        "killed": killed,
        "returnCode": completed.returncode,
        "outputTail": tail,
    }


def main() -> None:
    results = [run_mutant(mutant) for mutant in MUTANTS]
    survivors = [result["mutationId"] for result in results if not result["killed"]]
    receipt = {
        "status": "PASS" if not survivors else "FAIL",
        "mutantCount": len(results),
        "killedCount": len(results) - len(survivors),
        "survivors": survivors,
        "results": results,
    }
    target_value = os.environ.get("G6_MUTATION_RECEIPT_PATH")
    if target_value:
        target = Path(target_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": receipt["status"],
        "mutant_count": receipt["mutantCount"],
        "killed_count": receipt["killedCount"],
        "survivors": survivors,
    }, sort_keys=True))
    if survivors:
        raise SystemExit(f"critical mutants survived: {survivors}")


if __name__ == "__main__":
    main()
