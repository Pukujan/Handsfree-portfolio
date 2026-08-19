# Project State

**Project:** Handsfree Portfolio
**State:** G1 PUBLIC KNOWLEDGE ACTIVE
**Control ledger:** GitHub Issue #1
**Completed gate:** Issue #2 (G0) — PASS, receipt `docs/receipts/G0-FOUNDATION.md`
**Current executable gate:** Issue #3 (G1)
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

## Current evidence

G0 is complete. Verification PR #14 merged after full CI PASS. Final receipt-head verification run `32295376606` passed web install/build/tests, Python install, architecture boundary checks, JSON contract validation, and API/property tests.

## Current authorization — G1

Implement the narrow public FOSSIL knowledge boundary required by Slice 1. Do not broaden into the full career graph yet.

Required initial scope:
- Pujan identity only where needed for Slice 1;
- FOSSIL project identity and architecture claims needed for “What is FOSSIL and why does it matter?”;
- evidence for durable truth vs Graphiti/Neo4j projection;
- explicit public pack manifest and source revision provenance;
- public runtime read-only mount semantics;
- graph projection contract and destructive rebuild oracle.

Do not ingest private repositories, employer/client data, private study logs, or broad career history in G1.

### Slice 1 target

Hands-free recruiter conversation:
- “What is FOSSIL and why does it matter?”
- grounded public evidence answer;
- spoken response + evidence presentation;
- automatic relisten;
- follow-up “Why not just use Neo4j?” resolved against FOSSIL context;
- no private knowledge, graph authority shortcut, unsupported renderer expansion, or stale-turn publication.

## Gate order

- [x] #2 G0 Foundation
- [ ] #3 G1 Public FOSSIL knowledge pack
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
