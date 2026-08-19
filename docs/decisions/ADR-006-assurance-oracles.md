# ADR-006 — Assurance uses deterministic machine oracles and blinded humans for naturalness

Status: Accepted for machine-assurance harness; full G6 qualification remains pending human evidence.

## Context

The portfolio now contains authority-sensitive behavior across FOSSIL pack isolation, current evidence, conversation generations, grounding, cache eligibility, browser interruption, and latency-facing UI. G6 must test these behaviors without allowing the test system itself to become a second source of truth.

Naturalness creates a separate problem: prior research and project guidance show that LLM judges can be biased toward assistant-like output and do not reliably substitute for human conversational preference. Synthetic agents are useful workload generators, not final evaluators.

## Decision

G6 uses a strict oracle hierarchy.

### Deterministic machine authority

Correctness, security, privacy, lifecycle, generation ownership, evidence identity, cache eligibility, interruption, fallback, and latency-truth properties are judged by deterministic tests or protocol invariants.

The property catalog in `assurance/catalog/properties-v1.json` names each property, criticality, oracle, executable test path, and mutation targets.

### Mutation adequacy

Critical properties require mutation-kill evidence. `scripts/verify_g6_mutations.py` temporarily modifies exact production source, runs the named oracle, requires the oracle to fail, and restores the original source byte-for-byte in `finally`.

A critical mutant that survives blocks machine assurance. The accepted machine run killed all ten declared critical mutants.

### Synthetic personas

Persona simulators may generate recruiter/adversarial workload and stress conversation trajectories. Their output is not an answer key and does not constitute naturalness evidence.

### Model judges

Model judges, if introduced later, are auxiliary only. They may assist triage, clustering, or diagnostics but cannot close naturalness qualification and cannot override deterministic correctness or privacy oracles.

### Blinded humans

Blinded human raters are the final authority for conversational naturalness and pairwise preference. G6 therefore has two independently visible states:

- `MACHINE_ASSURANCE_PASS`
- human qualification: `PASS`, `FAIL`, `INCONCLUSIVE`, or `REQUIRED`

The gate is fully PASS only when machine assurance is PASS and the blinded human qualification protocol passes.

## Latency acknowledgement policy

Conversational delay acknowledgements are observational behavior, not decorative personality prompting.

The browser may show one fixed, non-factual acknowledgement only when:

1. a real `retrieval.started` event has been received;
2. that same generation is still in the `retrieving` state;
3. no evidence/plan/cancellation/completion has arrived; and
4. 1.4 seconds have elapsed since retrieval began.

The acknowledgement is visual status only and is cancelled when qualifying work stops. The 1.4-second value is a product policy subject to later human qualification; it is not treated as a universal human-factors constant.

## Holdout separation

Hidden expected answers and blinded naturalness items are not committed to the public repository. Public code contains only schemas and protocols. A sealed qualification bundle is mounted only into an isolated evaluation environment, and public receipts may record bundle IDs, digests, and aggregates but not hidden expected answers or raw rater identities.

## Consequences

Positive:
- test generation cannot silently redefine truth;
- machine correctness is reproducible and mutation-tested;
- naturalness is not self-certified by the same class of model under test;
- missing human evidence remains explicitly visible rather than converted into a fake green check.

Costs:
- G6 cannot be fully automated end-to-end;
- candidate/baseline revisions must be frozen before human collection;
- hidden holdout administration requires an external evaluator or private qualification environment.

This is intentional. Human conversational preference is the genuine external gate for G6.
