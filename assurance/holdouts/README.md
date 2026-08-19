# G6 sealed holdouts

This public repository contains holdout contracts, not hidden expected answers.

Three evaluation classes are supported:

- `retrieval`: unseen public questions with expected claim/evidence targets;
- `conversation`: unseen multi-turn recruiter trajectories with machine-verifiable behavior targets;
- `naturalness`: corpus-derived interaction situations with expected non-factual strategy/behavior targets.

Development agents and normal public CI must not receive the hidden expected-answer side after a qualification bundle is frozen. The sealed bundle may live in a private repository, encrypted CI artifact/secret, or another isolated evaluation store and is mounted only into a qualification job.

## Bundle contract

A sealed bundle provides a `manifest.json` plus one or more item files. The manifest records a bundle ID, schema version, SHA-256 digest for every item, evaluator owner, creation timestamp, class, and scoring authority.

Public receipts may record only bundle IDs/digests and aggregate metrics; hidden expected answers are not copied back into the public repository.

## Naturalness authority

Naturalness expectations are derived from versioned public human-dialogue corpora and peer-reviewed human-vs-LLM research under `assurance/conversation/`. The naturalness holdout is scored by deterministic corpus-derived behavior oracles. Synthetic conversations may generate stress workload but are not human ground truth. LLM-as-judge scores remain auxiliary only.

## Separation rule

Naturalness data is style-only and cannot create portfolio facts, evidence, permissions, or FOSSIL authority. A development-time simulator or matcher must not read hidden expected labels after holdout freeze.

## CI behavior

Public G6 CI validates the holdout interface and verifies that no files under `assurance/holdouts/private/` are committed. Absence of a final private qualification bundle does not fail correctness/security machine assurance; it keeps the corpus-naturalness qualification explicitly pending.
