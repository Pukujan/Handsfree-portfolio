import type { ConversationState, ConversationStreamClient, TurnEvent } from './conversation';
import { DEFAULT_LATENCY_BRIDGE_MS, latencyBridgeFor } from './latencyBridge';
import type { SpeechInputErrorCode, SpeechInputPort, SpeechOutputPort } from './voice';

export type EvidenceView = {
  evidenceId: string;
  sourceRef: string;
  label: string;
};

export type TranscriptTurn = {
  role: 'user' | 'portfolio';
  text: string;
  generation?: number;
};

export type HandsFreeSnapshot = {
  handsFreeEnabled: boolean;
  voiceInputSupported: boolean;
  voiceOutputSupported: boolean;
  state: ConversationState;
  statusLine: string;
  interimTranscript: string;
  lastQuestion: string;
  answerText: string;
  evidence: EvidenceView[];
  transcript: TranscriptTurn[];
  activeGeneration: number;
  activeSubject: string | null;
  error: string | null;
};

type Listener = () => void;

const initialSnapshot = (
  voiceInputSupported: boolean,
  voiceOutputSupported: boolean,
): HandsFreeSnapshot => ({
  handsFreeEnabled: false,
  voiceInputSupported,
  voiceOutputSupported,
  state: voiceInputSupported ? 'idle' : 'fallback',
  statusLine: voiceInputSupported
    ? 'Tap once, then just talk.'
    : 'Voice input is unavailable here. Type a question instead.',
  interimTranscript: '',
  lastQuestion: '',
  answerText: '',
  evidence: [],
  transcript: [],
  activeGeneration: 0,
  activeSubject: null,
  error: null,
});

export class HandsFreeController {
  private snapshot: HandsFreeSnapshot;
  private readonly listeners = new Set<Listener>();
  private requestAbort: AbortController | null = null;
  private latencyBridgeTimer: ReturnType<typeof setTimeout> | null = null;
  private inputToken = 0;
  private speechToken = 0;
  private serverTurnComplete = false;
  private speechComplete = true;
  private suppressedGeneration = 0;
  private pendingAnswerText = '';
  private pendingEvidence: EvidenceView[] = [];

  constructor(
    private readonly conversationId: string,
    private readonly client: ConversationStreamClient,
    private readonly speechInput: SpeechInputPort,
    private readonly speechOutput: SpeechOutputPort,
  ) {
    this.snapshot = initialSnapshot(speechInput.isSupported(), speechOutput.isSupported());
  }

  getSnapshot = (): HandsFreeSnapshot => this.snapshot;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private patch(update: Partial<HandsFreeSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...update };
    for (const listener of this.listeners) listener();
  }

  private cancelLatencyBridge(): void {
    if (this.latencyBridgeTimer !== null) clearTimeout(this.latencyBridgeTimer);
    this.latencyBridgeTimer = null;
  }

  private scheduleLatencyBridge(generation: number): void {
    this.cancelLatencyBridge();
    const startedAt = Date.now();
    this.latencyBridgeTimer = setTimeout(() => {
      this.latencyBridgeTimer = null;
      const pending = this.snapshot.state === 'retrieving'
        && this.snapshot.activeGeneration === generation;
      const bridge = latencyBridgeFor(Date.now() - startedAt, pending);
      if (bridge) this.patch({ statusLine: bridge });
    }, DEFAULT_LATENCY_BRIDGE_MS);
  }

  startHandsFree(): void {
    if (!this.speechInput.isSupported()) {
      this.patch({
        handsFreeEnabled: false,
        state: 'fallback',
        error: 'Voice input is not supported by this browser.',
        statusLine: 'Voice input is unavailable here. Type a question instead.',
      });
      return;
    }
    this.patch({ handsFreeEnabled: true, error: null });
    this.startListening();
  }

  stopHandsFree(): void {
    this.cancelLatencyBridge();
    this.patch({ handsFreeEnabled: false, state: 'idle', statusLine: 'Hands-free mode is off.' });
    this.requestAbort?.abort();
    this.requestAbort = null;
    this.stopInput();
    this.stopSpeech();
  }

  interrupt(): void {
    this.cancelLatencyBridge();
    if (this.snapshot.activeGeneration > 0) {
      this.suppressedGeneration = Math.max(this.suppressedGeneration, this.snapshot.activeGeneration);
    }
    this.requestAbort?.abort();
    this.requestAbort = null;
    this.stopSpeech();
    this.patch({ state: 'interrupted', statusLine: 'Interrupted. Listening for your next question.' });
    if (this.snapshot.handsFreeEnabled) this.startListening();
  }

  async submitText(question: string): Promise<void> {
    await this.submitQuestion(question);
  }

  private isMeaningfulTranscript(value: string): boolean {
    const normalized = value.trim();
    return normalized.length >= 2 && /[\p{L}\p{N}]/u.test(normalized);
  }

  private startListening(): void {
    if (!this.snapshot.handsFreeEnabled || !this.speechInput.isSupported()) return;
    this.stopInput();
    const token = ++this.inputToken;
    this.patch({ state: 'listening', interimTranscript: '', statusLine: 'Listening…', error: null });
    this.speechInput.start({
      onInterim: (text) => {
        if (token !== this.inputToken) return;
        this.patch({ interimTranscript: text });
      },
      onFinal: (text) => {
        if (token !== this.inputToken) return;
        if (!this.isMeaningfulTranscript(text)) {
          this.patch({ interimTranscript: '', statusLine: 'Listening…' });
          return;
        }
        this.inputToken += 1;
        this.speechInput.stop();
        void this.submitQuestion(text);
      },
      onError: (code, detail) => {
        if (token !== this.inputToken) return;
        this.handleSpeechInputError(code, detail);
      },
      onEnd: () => {
        if (token !== this.inputToken) return;
        if (this.snapshot.handsFreeEnabled && this.snapshot.state === 'listening') {
          this.startListening();
        }
      },
    });
  }

  private stopInput(): void {
    this.inputToken += 1;
    this.speechInput.stop();
  }

  private stopSpeech(): void {
    this.speechToken += 1;
    this.speechOutput.stop();
    this.speechComplete = true;
  }

  private handleSpeechInputError(code: SpeechInputErrorCode, detail?: string): void {
    this.cancelLatencyBridge();
    this.stopInput();
    const terminal = code === 'not-allowed' || code === 'audio-capture' || code === 'unsupported';
    this.patch({
      handsFreeEnabled: terminal ? false : this.snapshot.handsFreeEnabled,
      state: 'fallback',
      error: detail || code,
      statusLine: terminal
        ? 'Microphone access is unavailable. You can keep using the text input.'
        : 'Voice input had a problem. You can retry or type instead.',
      interimTranscript: '',
    });
  }

  private async submitQuestion(question: string): Promise<void> {
    const normalized = question.trim();
    if (!this.isMeaningfulTranscript(normalized)) return;

    this.cancelLatencyBridge();
    this.stopInput();
    this.requestAbort?.abort();
    const abort = new AbortController();
    this.requestAbort = abort;
    this.serverTurnComplete = false;
    this.speechComplete = true;
    this.pendingAnswerText = '';
    this.pendingEvidence = [];

    this.patch({
      state: 'idle',
      statusLine: 'Sending your question…',
      interimTranscript: '',
      lastQuestion: normalized,
      answerText: '',
      evidence: [],
      error: null,
      transcript: [...this.snapshot.transcript, { role: 'user', text: normalized }],
    });

    try {
      for await (const event of this.client.streamTurn({
        conversationId: this.conversationId,
        question: normalized,
        signal: abort.signal,
      })) {
        this.handleTurnEvent(event);
      }
    } catch (error) {
      if (abort.signal.aborted) return;
      this.cancelLatencyBridge();
      this.patch({
        state: 'fallback',
        error: error instanceof Error ? error.message : String(error),
        statusLine: 'The portfolio assistant is unavailable. You can still browse or retry with text.',
      });
    } finally {
      if (this.requestAbort === abort) this.requestAbort = null;
    }
  }

  private handleTurnEvent(event: TurnEvent): void {
    if (event.generation <= this.suppressedGeneration) return;
    if (event.type !== 'turn.accepted' && event.generation < this.snapshot.activeGeneration) return;

    if (event.type === 'turn.accepted') {
      if (event.generation < this.snapshot.activeGeneration) return;
      this.cancelLatencyBridge();
      const activeSubject = typeof event.payload.activeSubject === 'string'
        ? event.payload.activeSubject
        : null;
      this.patch({
        activeGeneration: event.generation,
        activeSubject,
        statusLine: 'Question received.',
      });
      return;
    }

    if (event.generation !== this.snapshot.activeGeneration) return;

    switch (event.type) {
      case 'retrieval.started':
        this.patch({ state: 'retrieving', statusLine: 'Checking public evidence…' });
        this.scheduleLatencyBridge(event.generation);
        break;
      case 'evidence.found':
        this.cancelLatencyBridge();
        this.patch({ statusLine: 'Public evidence found.' });
        break;
      case 'answer.planned': {
        this.cancelLatencyBridge();
        const evidence = Array.isArray(event.payload.evidence) ? event.payload.evidence : [];
        this.pendingEvidence = evidence.flatMap((item) => {
          if (!item || typeof item !== 'object') return [];
          const value = item as Record<string, unknown>;
          if (
            typeof value.evidenceId !== 'string' ||
            typeof value.sourceRef !== 'string' ||
            typeof value.label !== 'string'
          ) return [];
          return [{
            evidenceId: value.evidenceId,
            sourceRef: value.sourceRef,
            label: value.label,
          }];
        });
        this.patch({ state: 'rendering', statusLine: 'Preparing a grounded answer…' });
        break;
      }
      case 'answer.delta': {
        const text = typeof event.payload.text === 'string' ? event.payload.text : '';
        this.pendingAnswerText = text;
        this.patch({ answerText: text, evidence: this.pendingEvidence });
        break;
      }
      case 'answer.grounded':
        this.cancelLatencyBridge();
        this.speakGroundedAnswer();
        break;
      case 'turn.complete':
        this.cancelLatencyBridge();
        this.serverTurnComplete = true;
        if (this.snapshot.state !== 'speaking') {
          this.patch({ state: 'complete', statusLine: 'Answer complete.' });
          this.maybeRelisten();
        }
        break;
      case 'turn.cancelled':
        this.cancelLatencyBridge();
        this.stopSpeech();
        this.patch({ state: 'cancelled', statusLine: 'That turn was cancelled before publication.' });
        break;
    }
  }

  private speakGroundedAnswer(): void {
    const text = this.pendingAnswerText.trim();
    if (!text) {
      this.patch({ state: 'error', error: 'Grounded event arrived without verified answer text.' });
      return;
    }
    if (!this.speechOutput.isSupported()) {
      this.speechComplete = true;
      this.patch({
        state: 'fallback',
        statusLine: 'Voice replies are unavailable. The grounded answer is shown as text.',
        transcript: [...this.snapshot.transcript, {
          role: 'portfolio',
          text,
          generation: this.snapshot.activeGeneration,
        }],
      });
      return;
    }

    const token = ++this.speechToken;
    this.speechComplete = false;
    this.patch({
      state: 'speaking',
      statusLine: 'Speaking… tap the orb to interrupt.',
      transcript: [...this.snapshot.transcript, {
        role: 'portfolio',
        text,
        generation: this.snapshot.activeGeneration,
      }],
    });
    this.speechOutput.speak(text, {
      onStart: () => {
        if (token === this.speechToken) this.patch({ state: 'speaking' });
      },
      onEnd: () => {
        if (token !== this.speechToken) return;
        this.speechComplete = true;
        if (this.serverTurnComplete) {
          this.patch({ state: 'complete', statusLine: 'Answer complete.' });
          this.maybeRelisten();
        }
      },
      onError: (detail) => {
        if (token !== this.speechToken) return;
        this.speechComplete = true;
        this.patch({
          state: 'fallback',
          error: detail || 'speech-output-error',
          statusLine: 'Voice playback failed. The grounded answer is still available as text.',
        });
      },
    });
  }

  private maybeRelisten(): void {
    if (
      this.snapshot.handsFreeEnabled &&
      this.serverTurnComplete &&
      this.speechComplete &&
      this.speechInput.isSupported()
    ) {
      this.startListening();
    }
  }
}
