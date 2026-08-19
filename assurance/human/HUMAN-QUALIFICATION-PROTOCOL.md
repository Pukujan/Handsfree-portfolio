# G6 blinded human qualification protocol

## Purpose

Human raters are the final authority for conversational naturalness and preference. Synthetic personas and model judges may generate or pre-screen workload, but they cannot close G6.

## Candidate and baseline

The candidate is the current grounded conversational portfolio using the exact release candidate revision under evaluation. The baseline is the same public knowledge/evidence set presented through a deliberately simpler text interaction that does not receive the candidate's dialogue-context or latency-behavior enhancements. Both conditions must expose the same factual authority and must not differ in what claims are allowed.

The evaluation owner must freeze both revisions before collecting ratings. Any behavior-changing commit after collection invalidates the result for release qualification.

## Blinding

Each rater sees anonymized condition labels and randomized pair order. They must not be told which condition is the candidate. The evaluator should avoid recruiting people who implemented the compared behavior for the primary preference panel.

## Required tasks

Use unseen recruiter-style trajectories from the sealed naturalness/conversation holdout. Include at least one terse first-contact question, one pronoun/reference follow-up, one challenge/correction, one evidence request, one interruption or impatient turn, and one unsupported/private request across the panel.

## Rating dimensions

For every paired trajectory, collect 1–7 ratings for naturalness, responsiveness to the actual question, concision, context carry, trustworthiness, and annoyance/assistantese. Also collect a forced pairwise preference: A, B, or tie, plus an optional free-text reason.

Do not ask raters to score factual correctness when the answer key is hidden from them; deterministic oracles evaluate factual/authority correctness separately.

## Minimum panel

Qualification requires at least 5 independent human raters and at least 20 blinded paired trajectory ratings in aggregate. More is preferred when disagreement is high.

## G6 acceptance rule

G6 human qualification passes only if all of the following are true:

1. deterministic machine assurance for the evaluated revision is PASS;
2. no critical privacy/grounding/authority incident occurs in the human sessions;
3. candidate pairwise preference exceeds baseline preference, excluding ties;
4. the candidate median naturalness rating is not lower than the baseline median;
5. the candidate median annoyance/assistantese rating is not worse than baseline;
6. no evaluator flags a repeated systematic failure that violates a critical property.

A result with insufficient sample size, a tie on pairwise preference, or missing blinding metadata is `INCONCLUSIVE`, not PASS.

## Receipt format

The human-evaluation owner records a machine-readable aggregate receipt containing:

```json
{
  "protocolVersion": "1.0.0",
  "candidateRevision": "<git sha>",
  "baselineRevision": "<git sha or immutable artifact id>",
  "holdoutBundleId": "<sealed id>",
  "raterCount": 0,
  "pairedRatings": 0,
  "candidatePreferred": 0,
  "baselinePreferred": 0,
  "ties": 0,
  "medianNaturalnessCandidate": 0,
  "medianNaturalnessBaseline": 0,
  "medianAnnoyanceCandidate": 0,
  "medianAnnoyanceBaseline": 0,
  "criticalIncidents": 0,
  "decision": "PASS|FAIL|INCONCLUSIVE"
}
```

Only aggregate results and sealed bundle digests belong in the public repository. Raw rater identity/contact data and hidden expected answers remain outside the public repo.
