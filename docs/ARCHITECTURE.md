# Architecture Contract

## 1. Product boundary

Handsfree Portfolio is a conversational interface over a public, provenance-backed career knowledge system. Static portfolio content must remain independently browseable.

## 2. Architectural style

Use modular MVC with hexagonal dependency direction.

```text
View / Delivery
React/Vite + FastAPI
        |
        v
Application
conversation use cases / retrieval orchestration / answer planning
        |
        v
Domain
turn state / claims / evidence refs / authority / eligibility
        ^
        |
Ports owned inward
        ^
        |
Adapters
FOSSIL / Graphiti-Neo4j / models / cache / speech / telemetry / object storage
```

Dependencies point inward. Framework/provider types do not leak into domain contracts.

## 3. Proposed repository modules

```text
apps/web/                  React/Vite view and browser delivery adapters
services/portfolio-ai/     FastAPI delivery/runtime composition
src/domain/                pure domain models and invariants
src/application/           use cases and orchestration
src/ports/                 interfaces owned by domain/application
src/adapters/              FOSSIL, graph, model, cache, speech, telemetry
contracts/                 schemas and property catalog
specs/                     executable/traceable behavior specifications
tests/                     deterministic, integration and property tests
evals/                     user/recruiter/adversarial evaluation
mutants/                   mutation config and receipts
docs/                      durable architecture/decision records
```

Physical language/package boundaries may evolve, but inward dependency direction is invariant.

## 4. Knowledge authority

Canonical knowledge is the authorized FOSSIL public-pack durable state:
- immutable source evidence;
- stable corpus identities;
- validated knowledge-changing events;
- pack/ontology contracts;
- provenance/history/lifecycle.

Graphiti/Neo4j is a rebuildable projection used for graph-local and multi-hop retrieval. It is not a second source of truth.

Vector/lexical indexes are projections. Cached answers are derived artifacts. Model outputs are proposals/renderings. None can create authority.

## 5. Public pack boundary

The internet-facing runtime mounts only explicit public portfolio packs. Initial Slice 1 uses only enough public knowledge to answer Pujan + FOSSIL questions.

Public runtime has no canonical write authority.

Contribution semantics must distinguish at least: `BUILT`, `IMPLEMENTED`, `TESTED`, `RESEARCHED`, `USED`, `DEPLOYED`, `SHIPPED`, `WORKED_AT`, `AUTHORED`, and `EVIDENCED_BY`.

## 6. Retrieval

Retrieval lanes compete behind ports:
1. deterministic exact lookup;
2. semantic retrieval;
3. hybrid semantic + graph-local traversal;
4. deeper graph/source verification when benchmark evidence justifies it.

Graph traversal is not automatically the default. It must demonstrate incremental value against simpler baselines.

## 7. Answer pipeline

```text
user turn
→ authorized retrieval
→ supported claim/evidence plan (`PortfolioAnswerV1`)
→ dialogue act
→ conversational renderer
→ post-render grounding verification
→ streamed visible/spoken response
```

The renderer may paraphrase supported propositions but may not invent a new factual proposition.

## 8. Conversation protocol

Every turn has a generation/turn identity. Only the newest live generation may publish or speak. Interruption/cancellation fences stale work.

Backend emits structured state events such as `turn.accepted`, `retrieval.started`, `evidence.found`, `answer.planned`, `answer.delta`, `answer.grounded`, `turn.complete`, and `turn.cancelled`.

UI thinking/retrieval animation must correspond to real state; no fake waiting.

## 9. Voice

Speech input/output are adapters over the same conversation path. Voice cannot bypass grounding or authority checks. Hands-free mode is a UI/application state: listen → answer → relisten until stopped/interrupted/error.

Text/static fallback remains first-class.

## 10. Cache

Cache stores answer artifacts, never truth. Eligibility is version/authority bound. Keys/validation incorporate the knowledge pack-set/revisions, retrieval policy, answer-contract version, context where relevant, and renderer/model policy where relevant.

Cache hits cannot bypass source eligibility, redaction/supersession handling, pack isolation, or grounding.

## 11. Theme/design system

Theme controls color, typography, component treatment, motion, layout density, and voice visualization. Theme cannot alter retrieval, pack mounts, grounding, privacy, claims, or answer authority.

`bakery-v1` is the initial theme, not application architecture.

## 12. Production topology

Initial target:
- VPS + Docker Compose;
- Caddy public TLS/reverse-proxy boundary;
- React/Vite frontend;
- FastAPI conversation service;
- Graphiti/Neo4j on private Docker network;
- FOSSIL durable evidence/events through provider-neutral S3 adapter to R2 candidate;
- graph storage persisted operationally but assumed destroyable/rebuildable.

Neo4j/Bolt/browser ports are not public.

## 13. Recovery invariant

Destroying Neo4j/Graphiti storage must not destroy career knowledge. A fresh projection can be rebuilt from authorized FOSSIL durable state and pass semantic/retrieval invariants.

## 14. Static fallback

If voice, graph, model, cache, or AI API is unavailable, portfolio pages still expose projects, experience, research, education/resume and contact information.
