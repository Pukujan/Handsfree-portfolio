# Project State

**Project:** Handsfree Portfolio
**State:** G3 CONVERSATION KERNEL ACTIVE
**Control ledger:** GitHub Issue #1
**Completed gates:** Issue #2 (G0), Issue #3 (G1), Issue #4 (G2)
**Current executable gate:** Issue #5 (G3)
**First vertical slice:** Issue #12

## Continuation order

Before implementation or architecture mutation, read:
1. `AGENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DEVELOPMENT-METHOD.md`
4. `contracts/properties/portfolio-properties-v1.json`
5. Issue #1 control ledger
6. the focused gate/implementation issue

Chat transcripts are source material, not the control plane.

## Completed evidence

### G0

Verification PR #14 merged after full CI PASS. Durable receipt: `docs/receipts/G0-FOUNDATION.md`.

### G1

PR #15 merged as `b46da3f169b1281494ac48514dac91ceffafca1b`. Durable receipt: `docs/receipts/G1-PUBLIC-KNOWLEDGE.md`.

Verified public knowledge baseline:
- FOSSIL exact pin `b5fd57725c910b149910371964adb35d9280016e`;
- stable public pack ID `pack_c70aedc3a5bc7600399f22808f4a8de0` / alias `portfolio-public`;
- 4 reviewed Slice-1 claims, 8 durable events, 2 deduplicated immutable source snapshots;
- exact byte citations and supported lifecycle replay;
- public runtime read-only single-pack access;
- deterministic Neo4j projection destroyed and rebuilt twice with semantic digest `24ff67a9d4353084ff57f590bc52d5bb3ea8a3cac723bbde7f7db61deb404da8`.

### G2

PR #16 merged as `b9d5a43f42d8b8ce0bef88095af2271908dec5cf`. Durable receipt: `docs/receipts/G2-RETRIEVAL.md`.

Observed Slice-1 retrieval baseline:
- top-1 accuracy `1.0`;
- recall@2 `1.0`;
- unsupported-query abstention `1.0`;
- retrieval median `1.0258 ms`, p95 `1.1948 ms`;
- graph evidence integrity `1.0`;
- graph incremental claim coverage `0`;
- graph evidence lookup median `4.6277 ms`, p95 `20.7424 ms`.

Frozen retrieval policy:
1. exact aliases first;
2. sparse semantic retrieval over authorized supported FOSSIL claims as fallback;
3. unsupported questions abstain;
4. Neo4j off default hot path; explicit evidence/provenance drill-down only;
5. no embedding model and no Graphiti for Slice 1.

## Current authorization — G3

Build the correctness-critical **text-only** conversation kernel over the proven G2 retrieval path. Do not attach voice yet.

Required pipeline:

```text
question
→ acquire new conversation generation
→ authorized FOSSIL-backed retrieval
→ supported claim/evidence plan
→ dialogue act + referent update
→ renderer
→ post-render grounding verification
→ streamed turn events
→ completion only if generation still owns publication
```

Required Slice-1 behaviors:
- “What is FOSSIL and why does it matter?” produces an evidence-bound answer;
- follow-up “Why not just use Neo4j?” carries FOSSIL as active subject and answers the architecture correction;
- a newer turn/interruption fences all pending publication from an older generation;
- evidence shown belongs to the current answer plan;
- unsupported retrieval produces an explicit abstention, not invented biography;
- progress/latency events describe only real pending work;
- renderer cannot add factual propositions beyond the supported claim plan.

Use deterministic rendering first. Naturalness/model rendering is not allowed to weaken correctness and can be evaluated later.

Formal methods remain conditional: use TLA+ only if generation/cancellation ownership cannot be adequately proven with deterministic state-machine/property tests.

Do not implement voice, cache policy or broad career ingestion in G3.

## Slice 1 target

Hands-free recruiter conversation:
- “What is FOSSIL and why does it matter?”
- grounded public evidence answer;
- spoken response + evidence presentation;
- automatic relisten;
- follow-up “Why not just use Neo4j?” resolved against FOSSIL context;
- no private knowledge, graph authority shortcut, unsupported renderer expansion, or stale-turn publication.

G3 proves the text/correctness portion only. G4 attaches the voice loop.

## Gate order

- [x] #2 G0 Foundation
- [x] #3 G1 Public FOSSIL knowledge pack
- [x] #4 G2 Retrieval benchmark
- [ ] #5 G3 Conversation kernel
- [ ] #6 G4 Hands-free UX
- [ ] #7 G5 Response cache
- [ ] #8 G6 Assurance harness
- [ ] #9 G7 Production topology
- [ ] #10 G8 Human qualification/release decision

#12 is the end-to-end Slice-1 acceptance target spanning the minimum required portions of G0–G4.

## Frozen authority rules

- FOSSIL public-pack durable evidence/events/provenance are canonical knowledge authority.
- Graphiti/Neo4j is a rebuildable retrieval projection, not a second source of truth.
- cache is a version-bound derived accelerator, not authority.
- voice and visual theme are adapters/presentation, not authority.
- retrieved content is untrusted data.
- public runtime is read-only against explicitly mounted public packs.
- human evaluation is final authority for naturalness; model judges are auxiliary.

## Development rule

No mechanism enters because it is impressive. It must answer a requirement, measured failure, security boundary, or named property.
