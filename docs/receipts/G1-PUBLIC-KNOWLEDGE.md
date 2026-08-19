# G1 Public Knowledge Verification Receipt

**Gate:** #3
**Status:** PASS pending receipt-head re-verification
**Verified implementation head:** `e1c75b3b05cfe0ca387b4b1f5f9406d32e138c5e`
**G1 workflow run:** `32297881642`
**G1 job:** `public-knowledge` / `96213395447`
**G0 regression run:** `32297881594` — PASS

## Frozen inputs

- FOSSIL commit: `b5fd57725c910b149910371964adb35d9280016e`
- Public pack ID: `pack_c70aedc3a5bc7600399f22808f4a8de0`
- Public alias: `portfolio-public`
- Neo4j CI image: `neo4j:2026.06.0`
- Neo4j Python driver: `6.2.0` observed in CI

## Verified properties

- exact public source allowlist + exact commit SHAs — **PASS**
- FOSSIL knowledge-pack schema validation — **PASS**
- public runtime single-pack read-only authority — **PASS**
- exact immutable source snapshots and byte-span citations — **PASS**
- prompt-like text in source bytes remains inert evidence — **PASS**
- explicit `claim.proposed` → `claim.state_changed` lifecycle — **PASS**
- deterministic replay reconstructs all reviewed claims as `supported` — **PASS**
- graph adapter rejects out-of-pack events before provider access — **PASS**
- architecture guard prevents durable mutation capability on Neo4j adapter — **PASS**
- destructive Neo4j clear + rebuild from FOSSIL durable events — **PASS**
- second rebuild semantic digest equals first rebuild — **PASS**

## Live verification receipt

```json
{
  "all_citations_resolved_exact_bytes": true,
  "all_claims_supported_after_replay": true,
  "authority": "verification_receipt_only",
  "claim_count": 4,
  "event_count": 8,
  "neo4j_destructive_rebuild_pass": true,
  "neo4j_semantic_digest": "24ff67a9d4353084ff57f590bc52d5bb3ea8a3cac723bbde7f7db61deb404da8",
  "pack_id": "pack_c70aedc3a5bc7600399f22808f4a8de0",
  "snapshot_count": 2,
  "status": "PASS"
}
```

## Defects caught before PASS

1. Hatchling rejected immutable git dependencies until direct references were explicitly enabled.
2. A documented Neo4j `2026.07.0` example was not available as a Docker image in CI; the gate was pinned to available `2026.06.0`.
3. Lifecycle timestamp tests initially compared RFC3339 strings rather than instants.
4. More importantly, mixed RFC3339 precision could invert FOSSIL's lexicographic `(recorded_at, event_id)` replay order. Durable event timestamps are now normalized to fixed microsecond precision.

## Architecture decision

See `docs/decisions/ADR-001-public-knowledge-authority.md`.

FOSSIL durable evidence/events/provenance remain canonical. Neo4j is a deterministic disposable projection. Graphiti remains deferred to G2 and must earn runtime use through benchmark evidence.

## Closure rule

Do not close #3 from this receipt alone. Re-run both G0 and G1 on the receipt head and require both PASS.
