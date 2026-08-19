# Development Method — SDD + PDD

## Purpose

Build Handsfree Portfolio from explicit behavior specifications and named system properties rather than from implementation-first feature accumulation.

## 1. Specification-driven development

Each implementation issue begins with observable behavior and authority constraints.

A specification should state:
- actor/user/system goal;
- preconditions and mounted authority;
- input/event;
- externally observable result;
- failure/degradation result;
- affected property IDs;
- evidence/oracle that proves acceptance.

Prefer behavior language over implementation details. Example:

```gherkin
Scenario: recruiter follows up about Neo4j
  Given the active subject is FOSSIL
  And the prior answer established Neo4j as a FOSSIL projection
  When the recruiter asks "why not just use Neo4j?"
  Then the question resolves to the FOSSIL architecture
  And the answer uses authorized public evidence
  And no unsupported biography is added
```

## 2. Property-driven development

The property catalog is a durable contract. Critical properties have stable IDs and should identify:
- statement;
- criticality;
- owning boundary/module;
- deterministic oracle(s);
- property/state-machine test strategy;
- mutation target(s);
- hidden-holdout requirement if applicable;
- formal-method reference only when justified.

Properties are broader than example scenarios. Scenarios demonstrate important journeys; properties generalize over generated histories/inputs/failures.

## 3. Oracle hierarchy

Use the least expensive trustworthy oracle:
1. deterministic comparison/schema/permission oracle;
2. unit/contract test;
3. integration test against fake/disposable real adapter;
4. property-based generator/state machine;
5. mutation testing to prove the suite detects critical bypasses/inversions;
6. formal model for meaningful concurrent/state protocol risk;
7. human evaluation for naturalness/usability.

LLM evaluation may assist but is not final proof of critical correctness or naturalness.

## 4. Mutation testing

Mutation testing is required for critical rules where ordinary coverage can pass while semantics are wrong. Seed/focus mutations include:
- disable public-pack filter;
- accept stale/superseded evidence;
- treat graph result as canonical authority;
- bypass cache eligibility/version validation;
- reuse previous-turn citation;
- remove generation fence;
- permit renderer factual expansion;
- invert supported/unsupported result;
- always/never emit latency bridge;
- continue speaking after interruption.

A surviving critical mutant is a release blocker until classified as equivalent/non-actionable with evidence or killed by stronger tests.

## 5. User-behavior testing

Synthetic user agents generate workload, not truth. Required behavior profiles include rushed recruiter, nontechnical recruiter, technical hiring manager, skeptical staff engineer, impatient user, typo-heavy mobile user, privacy challenger, prompt attacker, and accessibility/keyboard user.

Test multi-turn behavior: pronouns, topic switches, correction, interruption, ambiguity, long pauses/backchannels, retrieval delay, missing evidence, graph/cache outage, and prompt-like source text.

Humans remain final authority for conversational naturalness and usefulness.

## 6. Hidden holdouts

Maintain separate sealed sets for:
- retrieval/evidence questions;
- unseen multi-turn conversation trajectories;
- human naturalness/preference comparisons.

Development agents should not receive expected answers for hidden acceptance sets. Scoring should expose only the minimum receipt needed to classify pass/fail.

## 7. Formal methods trigger

Do not model the entire product in TLA+ merely for sophistication. A formal model is justified when a concurrency/state protocol remains materially risky after deterministic/state-machine/property tests — likely candidates are turn generation ownership, cancellation, streaming publication, and interruption.

## 8. Gate completion

Each gate closes with reproducible receipts and explicit `DONE`, `BLOCKED`, or release decision. Happy-path demo success does not close a gate when critical properties, mutations, or failure paths remain unproven.
