# G6 sealed holdouts

This public repository contains **holdout contracts, not hidden expected answers**.

Three sealed evaluation sets are required:

- `retrieval`: unseen public questions with expected claim/evidence targets;
- `conversation`: unseen multi-turn recruiter trajectories with machine-verifiable behavior targets;
- `naturalness`: blinded human preference items and ratings.

Development agents and normal public CI must not receive the hidden expected answers. The sealed bundle should be stored outside this repository (for example a private repository, encrypted CI secret/artifact, or a human-administered evaluation system) and mounted only into an isolated qualification job.

## Bundle contract

A sealed bundle must provide:

```text
manifest.json
retrieval/*.json
conversation/*.json
naturalness/*.json
```

`manifest.json` must include a bundle ID, schema version, SHA-256 digest for every item, evaluator owner, creation timestamp, and whether expected answers are machine- or human-scored. Public receipts may record only bundle ID/digests and aggregate results; they must not copy hidden expected answers back into this repository.

## Separation rule

A development-time simulator may generate workload, but it is not permitted to read the sealed expected-answer side of a holdout. A model judge may provide auxiliary scores, but the naturalness holdout is considered qualified only after blinded human ratings are recorded under the human qualification protocol.

## CI behavior

Public G6 CI validates that the holdout interface exists and that no files under `assurance/holdouts/private/` are committed. If an isolated environment supplies a private bundle, a qualification runner may consume it and emit aggregate receipts. Absence of the private bundle is **not** treated as a machine-assurance failure; it leaves the human/hidden qualification status explicitly pending.
