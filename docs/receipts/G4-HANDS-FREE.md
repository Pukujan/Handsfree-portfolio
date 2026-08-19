# G4 Hands-free UX verification receipt

Gate: G4
Issue: #6
PR: #18
Verified implementation head before receipt-only documentation commits: `d1d78a78b9ac32f52709a9ee2b2b21bd16177b8d`

## CI evidence

All inherited and G4 workflows completed successfully on the same implementation head:

- G0 foundation — run `32303981547` — PASS
- G1 public knowledge — run `32303981384` — PASS
- G2 retrieval benchmark — run `32303981497` — PASS
- G3 conversation kernel — run `32303981596` — PASS
- G4 hands-free UX — run `32303981489` — PASS

The G4 job passed workspace install, architecture boundary guard, hands-free controller/SSE/UI tests, and production web build.

## Behaviors verified by the G4 test suite and composition

- production composition uses the real SSE client, not the deterministic fake;
- browser speech is behind replaceable input/output ports;
- retrieval UI follows actual `retrieval.started` events;
- answer speech waits for `answer.grounded`;
- stale/cancelled generations are suppressed;
- interruption aborts current local delivery and returns to a replacement-question path;
- microphone denial/unsupported speech falls back to text;
- hands-free off disables auto-relisten;
- empty/noise transcripts do not create turns;
- conversation ID persists across follow-ups;
- static project browsing remains available without the assistant;
- mobile safe-area spacing, 16px input text, and reduced-motion behavior are present.

## Qualification boundary

This receipt proves deterministic browser-controller behavior and production build correctness in CI. It does not claim universal physical microphone/speaker interoperability across all browser/OS/device combinations.
