import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ConversationStreamClient, ServerConversationState, TurnEvent } from './conversation';
import { HandsFreeController } from './HandsFreeController';
import { DEFAULT_LATENCY_BRIDGE_MS } from './latencyBridge';
import type { SpeechInputCallbacks, SpeechInputPort, SpeechOutputCallbacks, SpeechOutputPort } from './voice';

const event = (type: TurnEvent['type'], payload: Record<string, unknown> = {}): TurnEvent => ({
  contractVersion: '1.0.0',
  turnId: 'turn-1',
  generation: 1,
  type,
  occurredAt: '2026-08-19T22:00:00Z',
  payload,
});

class Gate {
  private releaseFn: (() => void) | null = null;
  readonly promise = new Promise<void>((resolve) => { this.releaseFn = resolve; });
  release() { this.releaseFn?.(); }
}

class Client implements ConversationStreamClient {
  constructor(private readonly includeEvidenceBeforeGate: boolean, private readonly gate: Gate) {}
  async *streamTurn(): AsyncIterable<TurnEvent> {
    yield event('turn.accepted', { activeSubject: 'FOSSIL' });
    yield event('retrieval.started');
    if (this.includeEvidenceBeforeGate) yield event('evidence.found', { evidenceIds: ['ev-1'] });
    await this.gate.promise;
    yield event('turn.cancelled', { reason: 'test-finished' });
  }
  async getState(): Promise<ServerConversationState> {
    return { contractVersion: '1.0.0', activeGeneration: 0, state: 'idle', activeSubject: null, referents: {} };
  }
}

class NoopInput implements SpeechInputPort {
  isSupported() { return false; }
  start(_callbacks: SpeechInputCallbacks) {}
  stop() {}
}

class NoopOutput implements SpeechOutputPort {
  isSupported() { return false; }
  speak(_text: string, _callbacks: SpeechOutputCallbacks) {}
  stop() {}
}

async function flush() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

afterEach(() => vi.useRealTimers());

describe('HandsFreeController latency truthfulness', () => {
  it('bridges only after a real retrieval remains pending past the budget', async () => {
    vi.useFakeTimers();
    const gate = new Gate();
    const controller = new HandsFreeController('latency', new Client(false, gate), new NoopInput(), new NoopOutput());
    const pending = controller.submitText('What is FOSSIL?');
    await flush();
    expect(controller.getSnapshot().state).toBe('retrieving');
    expect(controller.getSnapshot().statusLine).toBe('Checking public evidence…');

    vi.advanceTimersByTime(DEFAULT_LATENCY_BRIDGE_MS - 1);
    expect(controller.getSnapshot().statusLine).toBe('Checking public evidence…');
    vi.advanceTimersByTime(1);
    expect(controller.getSnapshot().statusLine).toBe('Yeah — lemme check the public evidence.');

    gate.release();
    await flush();
    await pending;
  });

  it('cancels the bridge when evidence arrives before the budget', async () => {
    vi.useFakeTimers();
    const gate = new Gate();
    const controller = new HandsFreeController('latency-evidence', new Client(true, gate), new NoopInput(), new NoopOutput());
    const pending = controller.submitText('What is FOSSIL?');
    await flush();
    expect(controller.getSnapshot().statusLine).toBe('Public evidence found.');

    vi.advanceTimersByTime(DEFAULT_LATENCY_BRIDGE_MS * 3);
    expect(controller.getSnapshot().statusLine).toBe('Public evidence found.');

    gate.release();
    await flush();
    await pending;
  });
});
