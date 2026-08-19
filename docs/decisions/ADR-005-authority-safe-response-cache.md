# ADR-005 — Response cache is a version-bound derived optimization, never knowledge authority

Status: Accepted

## Context

G3 established that public answer text may be published only after current FOSSIL-supported claims and evidence are resolved and deterministic grounding verification passes. G5 reduces repeated-question latency without creating a second truth system or allowing old language to outrank current durable knowledge.

## Decision

The response cache stores only **turn-neutral derived answer artifacts**:

- rendered text;
- stable claim IDs;
- evidence IDs.

It never stores or replays an old `turn_id`, generation, canonical claim state, pack mutation, or authority decision.

### Cache eligibility key

A cache key is the SHA-256 digest of canonicalized material containing:

- normalized question;
- material conversation context (`activeSubject` + referents);
- exact public FOSSIL authority fingerprint;
- retrieval-policy revision;
- answer-contract version;
- renderer-policy version.

The shared cache adapter receives only the digest, not the raw question text.

### FOSSIL authority fingerprint

The authority fingerprint includes:

- mounted public pack IDs;
- every currently readable durable event, deterministically ordered;
- every readable redaction tombstone, deterministically ordered.

Including tombstones prevents a redaction from collapsing the namespace back to a pre-redaction event-set digest.

### Hit validation

A candidate hit is not publishable by itself. On every hit the application:

1. creates a fresh turn/generation context;
2. re-resolves each cached claim ID through the current FOSSIL-supported catalog;
3. rebuilds current evidence/source references;
4. verifies that current evidence IDs still match the cached artifact;
5. constructs a fresh `RenderedAnswer` using current evidence and the new turn identity;
6. reruns the deterministic grounding verifier;
7. applies all normal G3 generation-ownership fences before publication.

Only then is the candidate counted as a validated hit.

### Miss, stale candidate and outage behavior

- Authority/version changes produce a new key namespace and therefore a miss.
- A candidate whose claim/evidence/text no longer validates is rejected, deleted when possible, and falls through to normal retrieval.
- Cache failure or telemetry failure never becomes request failure; the request falls through to the normal G3 retrieval/grounding path.
- Abstentions are not cached as shared conclusions.

### Observable protocol

Cache behavior remains internal. No new public `cache.hit` event is added to the conversation protocol. A validated hit simply has no `retrieval.started` event because no retrieval executes; the existing evidence/plan/grounded publication sequence remains authoritative.

## Initial adapter

The first implementation is a bounded, process-local, thread-safe LRU cache. A distributed Redis cache is deliberately deferred until deployment topology and measured cross-process reuse justify the operational and privacy cost.

## Privacy boundary

The cached artifact type has no field for raw question text, transcript, user identity, session ID, or arbitrary metadata. Context that materially affects correctness contributes only to the hashed key. Cacheable answer content comes from the explicitly public FOSSIL catalog.

## Mutation and failure targets

The G5 gate explicitly fails implementations that:

- omit authority revision from cache eligibility;
- accept evidence drift without rejection;
- ignore supported-claim removal/supersession;
- allow redaction to reuse the previous authority namespace;
- replay forged cached language without grounding verification;
- share a context-dependent answer across materially different conversation contexts;
- treat cache outage as request failure.

The architecture guard additionally prevents the cache storage adapter from importing FOSSIL/Neo4j projection infrastructure or exposing canonical mutation methods.

## Performance result

On the accepted Slice-1 CI run, the first exact-source FOSSIL-backed turn took 5.5794 ms and the validated repeat took 2.6568 ms, saving 2.9225 ms (about 52%) while preserving current-source revalidation. This is an observed CI result, not a universal latency guarantee.

The current deterministic renderer performs no model call, so G5 saves zero model tokens today. The key/version contract is ready to account for a future model renderer if one is separately admitted.

## Consequences

Positive:
- repeated public questions can skip retrieval while preserving FOSSIL authority;
- lifecycle and privacy changes automatically change cache eligibility;
- cached language cannot self-certify;
- cache outages remain non-critical.

Costs:
- every hit still pays current authority fingerprinting, catalog/evidence resolution, and grounding verification;
- process-local cache reuse is limited to one service process;
- stale namespace entries may remain physically in the bounded LRU until eviction, but they are cryptographically ineligible after authority/version changes and cannot be served.

That final distinction is intentional: cache storage lifetime is not cache authority lifetime.
