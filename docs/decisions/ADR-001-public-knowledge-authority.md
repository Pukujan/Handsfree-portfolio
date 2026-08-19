# ADR-001 — Public knowledge authority and graph projection

**Status:** Accepted
**Date:** 2026-08-19
**Gate:** #3 / G1

## Context

Handsfree Portfolio needs a public career knowledge boundary that can support exact citations, lifecycle/history, semantic/graph retrieval and later caching without allowing a database, model or cache to silently become truth authority.

FOSSIL already defines the required durability model: immutable evidence/source snapshots, stable corpus identities, append-only knowledge events, versioned pack contracts and provenance/history. Graph storage is reconstructable.

## Decision

1. The public knowledge alias is `portfolio-public`; its durable FOSSIL identity is `pack_c70aedc3a5bc7600399f22808f4a8de0`.
2. Public runtime access is read-only and mounts only that stable pack ID.
3. Slice-1 source ingestion accepts only explicitly allowlisted public repository files at exact commit SHAs.
4. Source bytes are snapshotted before claim acceptance. Claims receive exact byte-span citations.
5. A reviewed claim is represented by `claim.proposed` followed by an explicit accepted lifecycle event to `supported`; ingestion is never equivalent to truth.
6. Neo4j is a disposable projection. Stable FOSSIL IDs are stored as node properties; Neo4j internal IDs are never semantic identity.
7. The first graph projection is deterministic and model-free. It materializes supported FOSSIL claim/evidence/source relationships directly from durable events.
8. Graphiti is not required in G1. G2 must benchmark whether richer Graphiti-based graph extraction materially improves retrieval before it is admitted to the hot path.
9. The graph adapter has no durable-event mutation capability. Architecture CI rejects durable-store imports or canonical mutation methods on the graph adapter.
10. Destroying the graph and rebuilding it from FOSSIL events must produce the same semantic digest.

## Consequences

- A graph outage cannot destroy career knowledge.
- Graph retrieval may improve answers, but graph results must resolve back to FOSSIL evidence before factual use.
- We avoid LLM/model credentials during projection rebuild.
- The graph implementation can later move to Graphiti, another graph database, or no graph at all without changing public pack identity.
- R2/object-store deployment is deferred to G7; G1 proves portable FOSSIL semantics and projection rebuildability first.

## Rejected alternatives

### Neo4j as source of truth
Rejected because it violates FOSSIL stable identity, provenance and rebuildability properties.

### Graphiti immediately on all source text
Rejected for G1 because it adds model-dependent extraction before the retrieval benchmark proves incremental value.

### Cache as knowledge store
Rejected. Cached responses are version-bound derived artifacts and cannot create authority.

## Verification

The G1 CI gate must prove exact-source policy, FOSSIL schema validation, claim lifecycle replay, citation integrity, pack isolation, graph non-authority and destructive Neo4j rebuild equivalence before #3 closes.
