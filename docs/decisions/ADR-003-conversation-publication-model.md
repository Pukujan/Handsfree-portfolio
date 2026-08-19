# ADR-003 — Conversation publication and generation ownership

**Status:** Accepted
**Date:** 2026-08-19
**Gate:** #5 / G3

## Context

The portfolio must support multi-turn conversation, interruption and later hands-free voice without allowing an older retrieval, renderer or network stream to publish after a newer user turn owns the conversation. It must also prevent stylistic rendering from adding unsupported factual propositions.

G0–G2 already establish:

- modular boundaries;
- a read-only public FOSSIL claim catalog;
- supported-claim lifecycle semantics;
- exact/sparse retrieval with abstention;
- Neo4j as optional evidence drill-down only.

G3 defines the publication protocol above those layers.

## Decision

1. **The server owns conversation generations.** Clients send a conversation ID and question, never a generation number.
2. `begin_turn` immediately increments the active generation for that conversation. A newer generation supersedes all older pending work.
3. Generation ownership is checked at every factual publication boundary: after retrieval, after evidence collection, after planning, before answer publication, after answer publication and before completion.
4. A superseded turn may emit a cancellation receipt, but it may not emit a factual `answer.delta`, `answer.grounded` or `turn.complete` after losing ownership.
5. `retrieval.started` is emitted only immediately before real retrieval work. No fake “thinking” event is emitted for presentation purposes.
6. The G3 renderer is deterministic and claim-bound. It can emit supported propositions plus fixed non-factual connective language only.
7. The grounding verifier independently recomputes the exact admissible G3 rendering. Claim IDs, evidence IDs, turn identity, generation and text must all match the supported plan.
8. **No factual answer text is streamed before grounding verification succeeds.** G3 performs full render → verify → publish. SSE streaming therefore streams verified turn events, not speculative model tokens.
9. Unsupported retrieval yields an explicit abstention with no evidence instead of forcing a nearest career claim.
10. Conversation referents are application state. Slice 1 keeps `FOSSIL` active across “Why not just use Neo4j?” and maps ordinary follow-up referents to that subject.
11. Runtime composition fails with HTTP 503 when real public FOSSIL state is unavailable. Production does not fall back to fake answers.
12. SSE is a delivery adapter. Voice in G4 consumes the same turn-event protocol and does not own grounding, retrieval or generation semantics.
13. The initial session store is in-memory. Durable cross-process session persistence is not required for Slice 1 and must earn admission from a concrete deployment/user requirement.
14. TLA+ is **not admitted for G3**. Deterministic concurrency tests and property tests currently prove the targeted generation/publication invariant. Reconsider formal modeling only if the state machine grows beyond what these oracles can convincingly cover.

## Verified adversarial behaviors

- a malicious renderer that appends an unsupported biographical claim is rejected before `answer.delta`;
- an evidence/catalog failure after retrieval fails closed before factual publication;
- a blocked generation N cannot publish after generation N+1 completes;
- arbitrary sequential turns produce monotonically increasing generations and exactly one terminal completion per successful turn;
- a claim transitioned from `supported` to `superseded` is no longer presented as current, even when an exact alias still names its stable ID.

## Consequences

- G4 can cancel local speech and start a new server turn without inventing a second conversation state machine.
- Natural-language model rendering is not required for correctness and can be evaluated independently later.
- Token-by-token model streaming is deliberately deferred because it would require a different pre-publication verification strategy.
- User-visible progress can be driven from actual backend events.
- A session-process restart currently loses conversational referents but does not lose canonical knowledge; static/text fallback remains possible.

## Rejected alternatives

### Client-owned generation numbers
Rejected because a stale or malicious client could attempt to publish an older generation as current.

### Stream model tokens while verifying afterward
Rejected for Slice 1 because unsupported factual text could become visible/spoken before the verifier rejects it.

### Voice-specific conversation state
Rejected because voice is presentation/transport and must not fork correctness semantics.

### Add TLA+ immediately
Rejected because the named concurrency invariant is currently covered by a deterministic blocked-retrieval race plus property tests. Formal complexity has not yet earned admission.

## Revisit triggers

Revisit this ADR if any of the following becomes necessary:

- multiple API replicas need shared live session ownership;
- partial/token streaming is required before full answer verification;
- retrieval fans out into concurrent branches whose cancellation/publication ownership is not convincingly covered by current state-machine tests;
- durable session restoration becomes a product requirement.
