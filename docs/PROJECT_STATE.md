# Project State

**Project:** Handsfree Portfolio
**State:** G4 HANDS-FREE UX ACTIVE
**Control ledger:** GitHub Issue #1
**Completed gates:** Issue #2 (G0), Issue #3 (G1), Issue #4 (G2), Issue #5 (G3)
**Current executable gate:** Issue #6 (G4)
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

### G3

PR #17 merged as `76c0bd9c789d124d39947fd1d4be26a00fc03475`. Durable receipt: `docs/receipts/G3-CONVERSATION.md`.

Verified conversation baseline:
- server-owned monotonic conversation generations;
- stale generation fenced before factual publication;
- no factual answer text published before grounding verification;
- deterministic claim-bound rendering rejects unsupported expansion;
- unsupported queries abstain with zero evidence;
- active subject `FOSSIL` survives the Neo4j follow-up;
- superseded claims disappear from current answers;
- SSE carries verified turn events only;
- runtime without real public FOSSIL state fails HTTP 503 rather than using fake production answers;
- blocked-retrieval concurrency race and Hypothesis generation properties PASS;
- final exact G0/G1/G2/G3 head green before merge.

## Current authorization — G4

Attach the locked hands-free mobile-first experience to the G3 SSE protocol. Voice remains a browser/application adapter and cannot own retrieval, grounding or conversation generations.

Required interaction:

```text
identity / static portfolio shell
→ one-tap hands-free enable
→ speech recognition listening
→ final meaningful transcript
→ POST question to G3 SSE endpoint
→ UI state changes only from actual server turn events
→ verified answer stored from `answer.delta`
→ speech begins only after `answer.grounded`
→ `turn.complete` + speech end + hands-free still enabled
→ automatic relisten
```

Required behaviors:
- `retrieving` UI appears only after real `retrieval.started`;
- `answer.delta` alone cannot trigger speech;
- `answer.grounded` may speak the already-verified answer text;
- `turn.cancelled` never speaks;
- interruption stops local speech, begins listening, and the next recognized question starts a new server generation; G3 fences old publication;
- microphone denial/unsupported browser degrades to text fallback without breaking static portfolio content;
- hands-free disabled means no automatic relisten;
- empty/noise transcript is not submitted;
- reduced-motion, mobile safe-area and keyboard-safe 16px text input are required;
- theme tokens may alter visual treatment/motion but not retrieval, evidence, permissions or answer semantics.

Use native browser speech APIs as replaceable first adapters where available. Do not make Web Speech API support part of the correctness domain. Keep a real network SSE client as the default application composition; deterministic fake clients exist only in tests.

Do not implement cache policy, model-based naturalization, broad career ingestion or deployment orchestration in G4.

## Slice 1 target

Hands-free recruiter conversation:
- “What is FOSSIL and why does it matter?”
- grounded public evidence answer;
- spoken response + evidence presentation;
- automatic relisten;
- follow-up “Why not just use Neo4j?” resolved against FOSSIL context;
- no private knowledge, graph authority shortcut, unsupported renderer expansion, or stale-turn publication.

G4 completes the interactive portion of Slice 1. G5 adds cache only after the uncached interaction is correct.

## Gate order

- [x] #2 G0 Foundation
- [x] #3 G1 Public FOSSIL knowledge pack
- [x] #4 G2 Retrieval benchmark
- [x] #5 G3 Conversation kernel
- [ ] #6 G4 Hands-free UX
- [ ] #7 G5 Response cache
- [ ] #8 G6 Assurance harness
- [ ] #9 G7 Production topology
- [ ] #10 G8 Human qualification/release decision

#12 is the end-to-end Slice-1 acceptance target spanning G0–G4.

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
