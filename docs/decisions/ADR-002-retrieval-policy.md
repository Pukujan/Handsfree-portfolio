# ADR-002 — Slice-1 retrieval policy

**Status:** Accepted
**Date:** 2026-08-19
**Gate:** #4 / G2

## Context

G1 established four supported public FOSSIL claims with exact evidence/citations plus a disposable Neo4j projection. G2 must decide which retrieval mechanisms belong on the runtime hot path without admitting complexity by default.

## Benchmarked mechanisms

1. deterministic exact aliases over authorized supported claim IDs;
2. synonym-expanded sparse semantic ranking over FOSSIL-supported claim text + exact cited text;
3. Neo4j evidence/source expansion from already-authorized claim IDs.

The current benchmark contains 12 Slice-1 questions spanning definition, architecture, graph rebuild, pack isolation, provenance and unsupported queries.

## Observed result

GitHub Actions run `32299070622`:

- top-1 accuracy: `1.0`;
- recall@2: `1.0`;
- precision@2: `0.9`;
- unsupported-query abstention accuracy: `1.0`;
- retrieval latency median: `1.0258 ms`;
- retrieval latency p95: `1.1948 ms`;
- graph evidence integrity vs FOSSIL catalog: `1.0`;
- graph incremental claim count: `0`;
- graph evidence lookup median: `4.6277 ms`;
- graph evidence lookup p95: `20.7424 ms`.

## Decision

For Slice 1:

1. Exact aliases are used first for high-confidence named intents.
2. Sparse semantic retrieval is the default fallback over authorized supported FOSSIL claim records.
3. Unsupported questions abstain rather than forcing a nearest claim.
4. Neo4j is **not** on the default retrieval hot path.
5. Neo4j may be used for explicit evidence/provenance drill-down after claim IDs are already authorized by FOSSIL-backed retrieval.
6. Embedding models are not required for Slice 1.
7. Graphiti is not required for Slice 1.
8. Graphiti/embeddings may be reconsidered only when a later expanded-career benchmark exposes a named correctness/coverage gap that simpler retrieval cannot meet.

## Rationale

The graph produced no incremental claim coverage on the current corpus and added measurable latency. Its useful contribution is evidence-path presentation, where it exactly matched FOSSIL evidence/snapshot IDs. Therefore graph traversal remains a derived explainability mechanism, not a discovery requirement for Slice 1.

## Consequences

- Slice-1 conversation can stay cheap, deterministic and fast before LLM answer rendering.
- There is no embedding/vector infrastructure dependency yet.
- No model is required to retrieve the authoritative claims.
- Graph outage does not block ordinary factual retrieval.
- Evidence UI can still show graph paths when users explicitly ask for proof/sources.
- Retrieval policy must be re-benchmarked when the public career pack expands beyond the four FOSSIL claims.

## Rejected alternatives

### Always query Neo4j
Rejected because it added no claim coverage on the benchmark and increased latency.

### Add embeddings now
Rejected because exact+sparse retrieval already achieved full benchmark top-1/recall/abstention.

### Add Graphiti now
Rejected because no benchmark failure requires model-driven graph extraction for Slice 1.
