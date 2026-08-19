# Handsfree Portfolio

A hands-free conversational portfolio for Pujan Bajracharya. The system answers recruiter and hiring-manager questions from a provenance-backed **public** career knowledge pack, speaks answers aloud, shows evidence on demand, and returns to listening automatically.

## Product thesis

This is not a résumé chatbot. The portfolio is a conversational interface over a durable, evidence-backed model of professional work.

The system must remain useful without AI: static projects, experience, research, education, and resume content remain browseable if conversational services fail.

## Authority model

Canonical career knowledge is FOSSIL durable evidence/events/pack contracts/provenance. Graphiti/Neo4j, vector/lexical indexes, caches, model outputs, and conversation transcripts are replaceable runtime/projection systems. They cannot create canonical authority.

The public runtime mounts only explicit public knowledge packs and has no write authority.

## First vertical slice

1. Open the portfolio.
2. Start hands-free mode once.
3. Ask: **“What is FOSSIL and why does it matter?”**
4. Retrieve authorized public FOSSIL evidence.
5. Produce an evidence-bound answer contract.
6. Render concise conversational language without adding facts.
7. Speak the answer and show evidence.
8. Return to listening.
9. Ask: **“Why not just use Neo4j?”**
10. Resolve the follow-up to FOSSIL and answer from the durable-truth vs projection architecture.

Only Pujan + FOSSIL knowledge is required for Slice 1.

## Engineering method

- modular MVC / hexagonal dependency boundaries first;
- specification-driven development (SDD);
- property-driven development (PDD);
- deterministic contract and integration tests;
- property-based state-machine testing;
- mutation testing for critical correctness/security rules;
- adversarial and user-behavior evaluation;
- human evaluation as the final naturalness oracle;
- formal methods only where a named concurrency/state risk justifies them.

## Project tracker

GitHub Issue #1 is the control ledger. Gate issues #2–#10 define the staged implementation and release criteria. Issues #11–#13 track bootstrap contracts, Slice 1, and the machine-readable property catalog.

## Core rule

> No mechanism enters the system because it demonstrates technical sophistication. It enters only because a named requirement, measured baseline failure, security boundary, or correctness property requires it.
