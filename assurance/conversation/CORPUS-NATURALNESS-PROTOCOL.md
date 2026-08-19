# G6 corpus-backed conversational naturalness protocol

## Purpose

G6 naturalness is qualified from public human-conversation research and reproducible behavioral measurements. The release gate does not require recruiting a new human panel, and an LLM judge cannot become the final oracle.

This layer is **style-only**. It may choose conversational moves, response length, acknowledgement, repair, context carry, and similar surface behavior. It cannot create factual propositions, evidence, pack permissions, or authority.

## Evidence hierarchy

1. Peer-reviewed human-vs-LLM research establishes measurable failure modes and target properties.
2. Human-human dialogue corpora provide source distributions and interaction structures when licensing permits analysis.
3. Derived aggregate statistics and categorical interaction patterns may be committed.
4. Raw external dialogue text is not committed by default.
5. Synthetic recruiter conversations may stress the system but are not human ground truth.
6. LLM-as-judge scores are auxiliary diagnostics only.

The versioned source registry is `corpus-manifest-v1.json`.

## Current measured properties

- dialogue-act fit;
- acknowledgements/backchannels when interaction state warrants them;
- context-specific continuation and referent carry;
- style accommodation, especially response-length/register matching;
- correction/repair behavior;
- turn economy and verbosity control;
- avoidance of repeated-question boilerplate and unsolicited closing offers.

## Retrieval admission sequence

### Stage A — deterministic baseline

`patterns-v1.json` stores categorical response strategies with research provenance and no dialogue text. `DeterministicPatternMatcher` ranks patterns using explicit categorical weights and deterministic tie-breaking.

`development-situations-v1.json` is a public development fixture. It proves the matcher contract but is **not** the final qualification holdout.

### Stage B — semantic matching

Embeddings are admitted only after a frozen corpus-derived holdout exists and a semantic matcher materially outperforms the deterministic matcher on declared metrics. The embedding path must remain style-only and may not retrieve factual authority.

### Stage C — discourse graph

A discourse/knowledge graph is admitted only if graph traversal materially improves held-out interaction-strategy retrieval over semantic matching or supplies a separately named correctness property. A graph that merely duplicates semantic retrieval is rejected.

## Holdout rule

The final naturalness holdout should be built from corpus-derived interaction situations and expected non-factual strategy labels. It may be stored outside the normal development path so its labels are not tuned against after freeze. The public receipt records its bundle ID/digest and aggregate metrics.

The holdout must never contain career facts or become part of FOSSIL authority.

## Gate state

The deterministic development baseline is a prerequisite, not a PASS. Until a frozen corpus-derived qualification holdout exists and the admitted matcher beats the simple control without authority regressions, G6 remains `CORPUS_NATURALNESS_QUALIFICATION_REQUIRED`.
