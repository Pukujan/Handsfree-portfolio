# Conversational behavior assurance

This directory contains the G6 style-only research registry, interaction-pattern catalog, development benchmark, and corpus-naturalness protocol.

No external dialogue transcript is vendored here. Patterns contain only categorical interaction features and research source IDs. They are not evidence for portfolio facts.

Files:

- `corpus-manifest.schema.json` — source/provenance contract;
- `corpus-manifest-v1.json` — versioned papers and candidate human-dialogue datasets;
- `patterns-v1.json` — non-factual conversational strategies;
- `development-situations-v1.json` — public deterministic-baseline fixture, not the final holdout;
- `CORPUS-NATURALNESS-PROTOCOL.md` — admission and qualification policy.

Semantic retrieval and discourse-graph retrieval are intentionally absent until they beat the deterministic matcher on a frozen corpus-derived holdout.
