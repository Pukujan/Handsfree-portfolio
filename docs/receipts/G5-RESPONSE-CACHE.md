# G5 Response Cache verification receipt

Gate: G5
Issue: #7
PR: #19
Verified implementation head before receipt-only documentation commits: `c0b9e1d992e70d68c6727403d8e7421ca90b6b73`
Pinned FOSSIL revision: `b5fd57725c910b149910371964adb35d9280016e`

## CI evidence

All inherited gates and G5 completed successfully on the same implementation head:

- G0 foundation — run `32305562876` — PASS
- G1 public knowledge — run `32305562742` — PASS
- G2 retrieval benchmark — run `32305562586` — PASS
- G3 conversation kernel — run `32305562867` — PASS
- G4 hands-free UX — run `32305562618` — PASS
- G5 response cache — run `32305562543` — PASS

The G5 job passed architecture/contract guards plus 21 kernel/cache/API tests, two live FOSSIL verifiers, and uploaded both machine-readable receipts.

## Live repeated-question receipt

Observed on run `32305562543`:

- first grounded turn: **5.5794 ms**;
- validated cached repeat: **2.6568 ms**;
- observed latency saved: **2.9225 ms** (~52%);
- retrieval calls across the first two equal questions: **1**;
- validated hit skipped retrieval: true;
- hit received a fresh turn ID/generation: true;
- durable lifecycle change altered authority fingerprint: true;
- superseded claim was not served: true;
- forged cached text was rejected before publication: true;
- cache hit count: 1;
- validated hit count: 1;
- cache outages: 0;
- false-hit incidents: 0;
- model tokens saved: 0 (the accepted renderer is deterministic and does not call a model).

The post-lifecycle turn forced normal retrieval and completed in 2.4766 ms. Timing is observational CI evidence, not a production SLO.

## Live redaction receipt

A separate exact-source FOSSIL workspace established a normal miss and validated hit, then redacted the `claim.state_changed` support event using FOSSIL's durable redaction API.

Verified:

- pre-redaction validated hit: true;
- redaction tombstone present: true;
- authority fingerprint changed after redaction: true;
- post-redaction turn forced normal retrieval: true;
- redacted support was not served: true;
- retrieval calls across miss → hit → redaction: 2;
- false-hit incidents: 0.

The authority fingerprint also has a unit property proving a redaction tombstone changes the digest even when the live event set is empty, so privacy transitions cannot collapse back to an earlier namespace.

## Mutation/failure coverage

The executable G5 suite covers the Issue #7 targets:

- omit authority revision from eligibility → killed by key/revision tests;
- return a hit without current evidence eligibility → killed by evidence-drift test;
- ignore supersession/lifecycle change → killed by live lifecycle verifier;
- ignore redaction → killed by live tombstone verifier and tombstone-fingerprint property;
- share context-dependent answer globally → killed by cross-context test;
- replay forged cached language → killed by grounding-verifier test;
- treat cache outage as request failure → killed by outage-fallback test.

## Authority boundary

The cache remains a bounded derived optimization. It cannot create/promote claims, cannot bypass pack isolation/source resolution/grounding, and cannot publish stale language solely because an artifact exists. The architecture guard prevents the storage adapter from importing FOSSIL/Neo4j authority infrastructure or exposing canonical mutation methods.

Physical stale entries may remain until bounded-LRU eviction, but any authority/version change makes their old digest namespace ineligible. Storage lifetime is not authority lifetime.
