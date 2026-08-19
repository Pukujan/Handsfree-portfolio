# Project State

**Project:** Handsfree Portfolio
**State:** G2 RETRIEVAL BENCHMARK ACTIVE
**Control ledger:** GitHub Issue #1
**Completed gates:** Issue #2 (G0), Issue #3 (G1)
**Current executable gate:** Issue #4 (G2)
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

PR #15 merged as `b46da3f169b1281494ac48514dac91ceffafca1b`.
Durable receipt: `docs/receipts/G1-PUBLIC-KNOWLEDGE.md`.

Verified public knowledge baseline:
- FOSSIL exact pin `b5fd57725c910b149910371964adb35d9280016e`;
- stable public pack ID `pack_c70aedc3a5bc7600399f22808f4a8de0` / alias `portfolio-public`;
- 4 reviewed Slice-1 claims, 8 durable events, 2 deduplicated immutable source snapshots;
- exact byte citations and supported lifecycle replay;
- public runtime read-only single-pack access;
- deterministic Neo4j projection destroyed and rebuilt twice with semantic digest `24ff67a9d4353084ff57f590bc52d5bb3ea8a3cac723bbde7f7db61deb404da8`;
- Graphiti deferred until retrieval benchmark evidence justifies it.

## Current authorization — G2

Benchmark retrieval over the authoritative supported-claim catalog before adding runtime complexity.

Required question classes for the narrow Slice-1 corpus:
- direct identity/definition: “What is FOSSIL?”;
- architecture correction: “Why not just use Neo4j?”;
- authority/provenance: “What is actually durable?” / “What proves that?”;
- pack/security: “How does FOSSIL stop a query from reading everything?”;
- graph authority challenge: “Can Neo4j create truth?”;
- irrelevant/unsupported query requiring abstention.

Baseline order:
1. deterministic exact/alias lookup;
2. simple sparse/lexical ranking over supported public claims;
3. graph-local retrieval over the disposable Neo4j projection;
4. richer embedding/Graphiti retrieval only if a named benchmark gap remains.

G2 must measure correctness/coverage, citation resolvability, abstention behavior and latency. Graph or embedding mechanisms enter the hot path only where they materially improve a named benchmark class.

Do not add answer generation, voice behavior or caching policy in G2.

## Slice 1 target

Hands-free recruiter conversation:
- “What is FOSSIL and why does it matter?”
- grounded public evidence answer;
- spoken response + evidence presentation;
- automatic relisten;
- follow-up “Why not just use Neo4j?” resolved against FOSSIL context;
- no private knowledge, graph authority shortcut, unsupported renderer expansion, or stale-turn publication.

## Gate order

- [x] #2 G0 Foundation
- [x] #3 G1 Public FOSSIL knowledge pack
- [ ] #4 G2 Retrieval benchmark
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
