# G3 Conversation Kernel Verification Receipt

**Gate:** #5
**Status:** PASS pending final receipt-head re-verification
**Verified implementation head:** `8473ca16df4d73f667b57c17798225686e74cb7d`
**G3 workflow run:** `32300730059`
**G3 job:** `conversation-kernel` / `96222414216`
**Verification artifact:** `g3-conversation-receipt` / artifact `9382902104`
**Artifact digest:** `sha256:11d914422fe0a8c8becbe29a7306b3535e1b92a83344bf93d0c9830f9b5eaba8`

## Same-head regression status

- G0 `32300730054` — PASS
- G1 `32300730051` — PASS
- G2 `32300730071` — PASS
- G3 `32300730059` — PASS

## Machine-readable live receipt

```json
{
  "active_subject": "FOSSIL",
  "authority": "verification_receipt_only",
  "contracts_valid": true,
  "first_claim_ids": [
    "clm_portfolio_fossil_durable_truth_0001"
  ],
  "first_generation": 1,
  "first_turn_ms": 4.1757,
  "followup_claim_ids": [
    "clm_portfolio_fossil_projection_0001",
    "clm_portfolio_fossil_durable_truth_0001"
  ],
  "followup_generation": 2,
  "status": "PASS",
  "superseded_claim_not_presented": true,
  "unsupported_abstained": true,
  "unverified_text_streamed": false
}
```

## Verified properties

- server-owned monotonic conversation generations — **PASS**
- blocked generation N cannot publish after N+1 owns the conversation — **PASS**
- active `FOSSIL` subject survives the Neo4j follow-up — **PASS**
- supported FOSSIL claims/evidence are bound into the answer plan — **PASS**
- malicious renderer factual expansion is rejected before `answer.delta` — **PASS**
- evidence/catalog failure fails closed before factual publication — **PASS**
- unsupported public question yields explicit abstention with zero evidence — **PASS**
- superseded claim is not presented as current — **PASS**
- shared `TurnEventV1`, `PortfolioAnswerV1` and `ConversationStateV1` contracts validate — **PASS**
- production API has no fake-answer fallback when the real public pack is absent — **PASS**
- SSE emits verified application events; no factual answer text precedes grounding verification — **PASS**

## Defects caught before PASS

1. The canonical Slice-1 opening question `What is FOSSIL and why does it matter?` was missing from exact aliases. Sparse retrieval correctly returned a broader set than the live verifier expected. The named product journey is now a deterministic exact alias and is included in the G2 benchmark as `q13`.
2. Verification evidence was initially console-only. G3 now emits a machine-readable CI artifact; the artifact is a verification receipt, not knowledge authority.

## Architecture decision

See `docs/decisions/ADR-003-conversation-publication-model.md`.

G3 uses full render → deterministic grounding verification → SSE publication. Token-by-token speculative model streaming and TLA+ are not admitted for Slice 1 because the current correctness properties are covered by deterministic/concurrency/property tests.

## Closure rule

Require G0, G1, G2 and G3 to pass on the final receipt/ADR head before closing #5.
