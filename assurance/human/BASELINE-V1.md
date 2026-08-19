# G6 Simple-Text Baseline v1

## Purpose

This artifact defines the deliberately simpler comparison condition for the blinded G6 human qualification panel. It is evaluation tooling only. It must not be merged into or substituted for the frozen G6 candidate.

## Frozen authority

Candidate backend revision:

`6174cc886aff82a4cfa3ae4f64ac79cfbf98b15d`

The baseline must call a deployment of that exact candidate revision. It therefore uses the same FOSSIL public-pack authority, retrieval policy, cache eligibility, claim/evidence planning, renderer and grounding verification as the candidate. The baseline is not allowed to introduce a different knowledge source, prompt, model, retriever or answer policy.

The immutable `baselineRevision` recorded in the human result is the exact Git commit containing this baseline runner after its dedicated CI verification passes.

## Deliberately removed enhancements

For every holdout turn, `scripts/run_g6_human_baseline.py`:

1. creates a fresh random conversation ID;
2. sends only that turn's question to the frozen candidate API;
3. never reuses server conversation state or referents across turns, including turns that belong to the same human-rated trajectory;
4. consumes the normal SSE authority/grounding path;
5. releases only the final text after both `answer.grounded` and `turn.complete` have been observed;
6. presents text only — no speech input/output, automatic relisten loop, latency bridge, thinking filler or voice presentation.

This intentionally removes dialogue-context carry and hands-free/latency presentation advantages while preserving factual authority and verification.

## Private input/output

The runner accepts a private JSONL file outside the public repository:

```json
{"itemId":"opaque-item-id","question":"unseen holdout question"}
```

It emits private JSONL containing the opaque item ID, question SHA-256, baseline/candidate revisions, generated conversation ID and answer text. The raw question is not copied into the output record.

Neither private holdout input nor baseline output is committed to this repository. Only the sealed bundle ID/digest and aggregate blinded human result may enter public gate evidence.

## Invocation

```text
python scripts/run_g6_human_baseline.py \
  --api-url <frozen-candidate-api> \
  --input <private-holdout.jsonl> \
  --output <private-baseline-output.jsonl> \
  --baseline-revision <exact-40-char-baseline-commit>
```

The evaluation owner must independently verify that `<frozen-candidate-api>` is running candidate revision `6174cc886aff82a4cfa3ae4f64ac79cfbf98b15d` before collecting panel material.

## Blinding boundary

This runner does not assign A/B labels or expose condition identity to raters. Pair-order randomization and anonymized condition labels belong to the sealed human-evaluation administration layer. The public repository must not receive hidden expected answers or raw rater identity/contact data.

## Failure behavior

A cancelled turn, malformed SSE event, missing answer text, missing `answer.grounded`, missing `turn.complete`, blank item/question, or malformed baseline revision is a hard baseline-generation failure. The tool must not silently substitute partial or ungrounded language.
