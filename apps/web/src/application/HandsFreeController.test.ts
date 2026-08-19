import { describe, expect, it } from 'vitest';
import type {
  ConversationStreamClient,
  ServerConversationState,
  TurnEvent,
} from './conversation';
import { HandsFreeController } from './HandsFreeController';
import type {
  SpeechInputCallbacks,
  SpeechInputPort,
  SpeechOutputCallbacks,
  SpeechOutputPort,
} from './voice';

const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

function event(
  type: TurnEvent['type'],
  generation: number,
  payload: Record<string, unknown> = {},
): TurnEvent {
  return {
    contractVersion: '1.0.0',
    turnId: `turn-${generation}`,
    generation,
    type,
    occurredAt: `2026-08-19T21:00:0${generation}Z`,
    payload,
  };
}

const evidence = [{
  evidenceId: 'ev-fossil',
  sourceRef: 'Pukujan/fossil-core@sha:ARCHITECTURE.md',
  label: 'FOSSIL architecture',
}];

function successfulEvents(generation: number): TurnEvent[] {
  return [
    event('turn.accepted', generation, { activeSubject: 'FOSSIL' }),
    event('retrieval.started', generation),
    event('evidence.found', generation, { evidenceIds: ['ev-fossil'] }),
    event('answer.planned', generation, { evidence }),
    event('answer.delta', generation, { text: 'Grounded answer.', evidenceIds: ['ev-fossil'] }),
    event('answer.grounded', generation, { evidenceIds: ['ev-fossil'] }),
    event('turn.complete', generation),
  ];
}

class Gate {
  private releaseFn: (() => void) | null = null;
  readonly promise = new Promise<void>((resolve) => { this.releaseFn = resolve; });
  release(): void { this.releaseFn?.(); }
}

type ScriptStep = TurnEvent | Gate;

class ScriptedClient implements ConversationStreamClient {
  calls: { conversationId: string; question: string }[] = [];
  constructor(private readonly scripts: ScriptStep[][]) {}

  async *streamTurn(input: { conversationId: string; question: string }): AsyncIterable<TurnEvent> {
    this.calls.push({ conversationId: input.conversationId, question: input.question });
    const script = this.scripts[this.calls.length - 1] || [];
    for (const step of script) {
      if (step instanceof Gate) await step.promise;
      else yield step;
    }
  }

  async getState(): Promise<ServerConversationState> {
    return {
      contractVersion: '1.0.0',
      activeGeneration: 0,
      state: 'idle',
      activeSubject: null,
      referents: {},
    };
  }
}

class FakeSpeechInput implements SpeechInputPort {
  callbacks: SpeechInputCallbacks | null = null;
  starts = 0;
  stops = 0;
  constructor(private supported = true) {}
  isSupported(): boolean { return this.supported; }
  start(callbacks: SpeechInputCallbacks): void { this.starts += 1; this.callbacks = callbacks; }
  stop(): void { this.stops += 1; }
  final(text: string): void { this.callbacks?.onFinal(text); }
  interim(text: string): void { this.callbacks?.onInterim(text); }
  error(code: Parameters<SpeechInputCallbacks['onError']>[0]): void { this.callbacks?.onError(code); }
  end(): void { this.callbacks?.onEnd(); }
}

class FakeSpeechOutput implements SpeechOutputPort {
  speaks: string[] = [];
  stops = 0;
  callbacks: SpeechOutputCallbacks | null = null;
  constructor(private supported = true) {}
  isSupported(): boolean { return this.supported; }
  speak(text: string, callbacks: SpeechOutputCallbacks): void {
    this.speaks.push(text);
    this.callbacks = callbacks;
    callbacks.onStart?.();
  }
  stop(): void { this.stops += 1; this.callbacks = null; }
  finish(): void { const value = this.callbacks; this.callbacks = null; value?.onEnd(); }
}

function controller(client: ScriptedClient, input = new FakeSpeechInput(), output = new FakeSpeechOutput()) {
  return { value: new HandsFreeController('conversation-1', client, input, output), input, output };
}

describe('HandsFreeController', () => {
  it('does not show retrieving until the backend emits retrieval.started', async () => {
    const gate = new Gate();
    const client = new ScriptedClient([[
      event('turn.accepted', 1, { activeSubject: 'FOSSIL' }),
      gate,
      ...successfulEvents(1).slice(1),
    ]]);
    const { value } = controller(client);
    const pending = value.submitText('What is FOSSIL?');
    await tick();
    expect(value.getSnapshot().state).toBe('idle');
    expect(value.getSnapshot().statusLine).toBe('Question received.');
    gate.release();
    await pending;
  });

  it('stores answer.delta but does not speak until answer.grounded', async () => {
    const gate = new Gate();
    const script = successfulEvents(1);
    const client = new ScriptedClient([[
      ...script.slice(0, 5),
      gate,
      ...script.slice(5),
    ]]);
    const { value, output } = controller(client);
    const pending = value.submitText('What is FOSSIL?');
    await tick();
    expect(value.getSnapshot().answerText).toBe('Grounded answer.');
    expect(output.speaks).toEqual([]);
    gate.release();
    await pending;
    expect(output.speaks).toEqual(['Grounded answer.']);
  });

  it('relistens only after grounded speech and server completion while hands-free remains enabled', async () => {
    const client = new ScriptedClient([successfulEvents(1)]);
    const { value, input, output } = controller(client);
    value.startHandsFree();
    const startsBeforeQuestion = input.starts;
    input.final('What is FOSSIL?');
    await tick();
    expect(output.speaks).toEqual(['Grounded answer.']);
    expect(input.starts).toBe(startsBeforeQuestion);
    output.finish();
    expect(value.getSnapshot().state).toBe('listening');
    expect(input.starts).toBe(startsBeforeQuestion + 1);
  });

  it('does not relisten when hands-free is turned off', async () => {
    const client = new ScriptedClient([successfulEvents(1)]);
    const { value, input, output } = controller(client);
    value.startHandsFree();
    input.final('What is FOSSIL?');
    await tick();
    const starts = input.starts;
    value.stopHandsFree();
    output.finish();
    expect(value.getSnapshot().handsFreeEnabled).toBe(false);
    expect(input.starts).toBe(starts);
  });

  it('microphone denial enters fallback but text questions still use the grounded stream', async () => {
    const client = new ScriptedClient([successfulEvents(1)]);
    const { value, input, output } = controller(client);
    value.startHandsFree();
    input.error('not-allowed');
    expect(value.getSnapshot().state).toBe('fallback');
    expect(value.getSnapshot().handsFreeEnabled).toBe(false);
    await value.submitText('What is FOSSIL?');
    expect(client.calls).toHaveLength(1);
    expect(output.speaks).toEqual(['Grounded answer.']);
  });

  it('ignores empty/noise finals instead of creating a server turn', async () => {
    const client = new ScriptedClient([]);
    const { value, input } = controller(client);
    value.startHandsFree();
    input.final('   ');
    input.final('!');
    await tick();
    expect(client.calls).toEqual([]);
    expect(value.getSnapshot().state).toBe('listening');
  });

  it('turn.cancelled never speaks', async () => {
    const client = new ScriptedClient([[
      event('turn.accepted', 1, { activeSubject: 'FOSSIL' }),
      event('retrieval.started', 1),
      event('turn.cancelled', 1, { reason: 'superseded' }),
    ]]);
    const { value, output } = controller(client);
    await value.submitText('What is FOSSIL?');
    expect(output.speaks).toEqual([]);
    expect(value.getSnapshot().state).toBe('cancelled');
  });

  it('interrupt stops speech and starts listening for the replacement question', async () => {
    const completionGate = new Gate();
    const script = successfulEvents(1);
    const client = new ScriptedClient([[
      ...script.slice(0, 6),
      completionGate,
      script[6],
    ]]);
    const { value, input, output } = controller(client);
    value.startHandsFree();
    input.final('What is FOSSIL?');
    await tick();
    expect(value.getSnapshot().state).toBe('speaking');
    const starts = input.starts;
    value.interrupt();
    expect(output.stops).toBeGreaterThan(0);
    expect(value.getSnapshot().state).toBe('listening');
    expect(input.starts).toBe(starts + 1);
    completionGate.release();
    await tick();
    expect(value.getSnapshot().state).toBe('listening');
  });

  it('ignores stale events from an older stream after a newer generation is accepted', async () => {
    const oldGate = new Gate();
    const old = successfulEvents(1);
    const client = new ScriptedClient([
      [old[0], old[1], oldGate, ...old.slice(2)],
      successfulEvents(2),
    ]);
    const { value, output } = controller(client);
    const first = value.submitText('What is FOSSIL?');
    await tick();
    const second = value.submitText('Why not just use Neo4j?');
    await second;
    expect(value.getSnapshot().activeGeneration).toBe(2);
    const speakCount = output.speaks.length;
    oldGate.release();
    await first;
    expect(value.getSnapshot().activeGeneration).toBe(2);
    expect(output.speaks).toHaveLength(speakCount);
  });

  it('keeps the same conversation id across follow-up submissions', async () => {
    const client = new ScriptedClient([successfulEvents(1), successfulEvents(2)]);
    const { value } = controller(client);
    await value.submitText('What is FOSSIL?');
    await value.submitText('Why not just use Neo4j?');
    expect(client.calls.map((call) => call.conversationId)).toEqual(['conversation-1', 'conversation-1']);
  });
});
