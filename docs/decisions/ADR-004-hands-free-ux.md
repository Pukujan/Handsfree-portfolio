# ADR-004 — Hands-free UX is an adapter over the grounded conversation kernel

Status: Accepted

## Context

G3 established the authority-critical conversation protocol: the server owns generations, retrieval, grounding, cancellation, and publication eligibility. G4 adds browser speech and a mobile-first conversational presentation without creating a second authority path.

## Decision

The browser hands-free experience is a replaceable presentation adapter over G3 SSE events.

- `FetchSseConversationClient` is the production conversation transport.
- `SpeechInputPort` and `SpeechOutputPort` isolate browser speech APIs at the edge.
- `HandsFreeController` owns local interaction orchestration only.
- Server `turn.accepted` generations remain authoritative.
- UI enters `retrieving` only after `retrieval.started`.
- `answer.delta` may be displayed, but speech is allowed only after `answer.grounded`.
- Cancelled, stale, or locally suppressed generations are never spoken.
- Microphone denial or unsupported browser speech degrades to text.
- Hands-free mode does not control static portfolio availability.
- Theme tokens may change presentation but not conversation semantics or authority.

## Interruption

Interruption stops local TTS and aborts the current HTTP stream. The next recognized or typed question creates a new server turn. G3 generation fencing remains the final stale-publication defense.

## Mobile and accessibility

The first presentation preset is `bakery-v1`. The shell is safe-area aware, preserves a 16px text input, supports keyboard/text operation, exposes transcript/evidence visually, and disables nonessential animation under `prefers-reduced-motion`.

## Rejected alternatives

- Browser voice owning turn IDs or generations.
- Speaking ungrounded deltas to reduce perceived latency.
- Showing a fake retrieval/thinking state before backend evidence work begins.
- Requiring microphone support to browse the portfolio.
- Using the deterministic fake conversation adapter in production composition.

## Qualification boundary

CI proves controller, SSE parsing, presentation state transitions, fallback behavior, and production build behavior with deterministic test doubles and jsdom. It does not prove universal real-device microphone interoperability across every browser/OS combination; that remains a deployment qualification item.
