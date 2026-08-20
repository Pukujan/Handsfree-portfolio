# G6 Machine Assurance receipt

Gate: G6
Issue: #8
PR: #20
Verified implementation head before receipt-only documentation commits: `9291dd03905118c472ad5fbf48f7688d4860ce13`
Pinned FOSSIL revision: `b5fd57725c910b149910371964adb35d9280016e`

## Status

**Machine assurance: PASS**

**Full G6 qualification: BLOCKED — blinded human naturalness/preference evidence is still required.**

This receipt does not close G6 and does not treat simulator/model evaluation as a substitute for human qualification.

## Exact-head regression evidence

All inherited gates and G6 completed successfully on the same implementation head:

- G0 foundation — run `32307319565` — PASS
- G1 public knowledge — run `32307319550` — PASS
- G2 retrieval benchmark — run `32307319553` — PASS
- G3 conversation kernel — run `32307319543` — PASS
- G4 hands-free UX — run `32307319536` — PASS
- G5 response cache — run `32307319584` — PASS
- G6 assurance — run `32307319569` — PASS

## G6 machine evidence

Run `32307319569` produced:

- architecture boundary guard: PASS;
- shared contract validation: PASS;
- Python cross-gate/property/adversarial/API suite: **40 passed**;
- web hands-free/latency/UI suite: **21 passed across 7 test files**;
- deterministic persona workload: **9 personas / 59 turns / 59 completed / 13 abstentions / 0 unsafe outcomes**;
- critical mutation harness: **10 killed / 10 total / 0 survivors**;
- property catalog: **13 named properties**;
- BDD journeys: **6**;
- adversarial behavior classes: **9**;
- hidden expected-answer files committed: **false**;
- model-judge authority: `auxiliary_only`;
- naturalness final authority: `blinded_humans`.

The emitted machine receipt reports:

```text
machineStatus = MACHINE_ASSURANCE_PASS
humanQualification = REQUIRED
overallGateStatus = HUMAN_QUALIFICATION_REQUIRED
```

## Machine-readable artifacts

G6 uploaded `g6-machine-assurance-receipts` as Actions artifact ID `9385166876`.

Artifact ZIP SHA-256:
`844076cd0c8530e46fca37139b15c6cf2590a68d3e5ba8d0cfef3d90b271f0be`

The artifact contains machine, mutation, and simulator JSON receipts. These receipts are verification evidence only; they do not create portfolio knowledge authority.

## Critical mutation result

The following production-source mutants were all killed by their named deterministic oracle:

1. public pack filter disabled;
2. stale evidence accepted;
3. prior citation/source metadata reused;
4. generation ownership fence skipped;
5. supported/current lifecycle logic inverted;
6. cache grounding validation bypassed;
7. renderer factual expansion allowed;
8. latency acknowledgement always emitted;
9. latency acknowledgement never emitted;
10. interruption allowed old speech to continue.

The mutation runner restores source byte-for-byte after every mutant.

## Latency-truth qualification

The browser latency acknowledgement is permitted only after 1.4 seconds of a real pending retrieval generation. It is cancelled on evidence, plan, grounding, completion, cancellation, interruption, replacement turns, or failure. Fast retrieval receives no fabricated acknowledgement.

This policy is machine-correct with respect to backend state; whether its threshold and phrasing improve perceived naturalness remains part of the human qualification.

## Remaining G6 exit condition

The blinded human protocol in `assurance/human/HUMAN-QUALIFICATION-PROTOCOL.md` requires, at minimum:

- at least 5 independent human raters;
- at least 20 blinded paired trajectory ratings;
- frozen candidate and baseline revisions;
- sealed holdout bundle ID/digests;
- zero critical privacy/grounding/authority incidents;
- candidate pairwise preference greater than baseline preference, excluding ties;
- candidate median naturalness not below baseline;
- candidate median annoyance/assistantese not worse than baseline.

A tie, insufficient sample, missing blinding metadata, or missing holdout evidence is `INCONCLUSIVE`, not PASS.

Once an aggregate human result is produced, an isolated qualification run can supply it as `G6_HUMAN_RESULT_PATH`; `scripts/verify_g6_machine.py` will validate the schema and derive the final G6 qualification state deterministically.

Until that happens, Issue #8 and PR #20 remain open and G7 must not be treated as the next qualified gate.
