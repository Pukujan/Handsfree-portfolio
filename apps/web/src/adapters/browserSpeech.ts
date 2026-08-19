import type {
  SpeechInputCallbacks,
  SpeechInputErrorCode,
  SpeechInputPort,
  SpeechOutputCallbacks,
  SpeechOutputPort,
} from '../application/voice';

type RecognitionResultLike = {
  isFinal: boolean;
  0: { transcript: string };
};

type RecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<RecognitionResultLike>;
};

type RecognitionErrorLike = { error?: string; message?: string };

type RecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: RecognitionEventLike) => void) | null;
  onerror: ((event: RecognitionErrorLike) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort?(): void;
};

type RecognitionConstructor = new () => RecognitionLike;

type SpeechWindow = Window & typeof globalThis & {
  SpeechRecognition?: RecognitionConstructor;
  webkitSpeechRecognition?: RecognitionConstructor;
};

function recognitionConstructor(): RecognitionConstructor | undefined {
  const value = window as SpeechWindow;
  return value.SpeechRecognition || value.webkitSpeechRecognition;
}

function mapRecognitionError(value: string | undefined): SpeechInputErrorCode {
  switch (value) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'not-allowed';
    case 'audio-capture':
      return 'audio-capture';
    case 'network':
      return 'network';
    case 'no-speech':
      return 'no-speech';
    case 'aborted':
      return 'aborted';
    default:
      return 'unknown';
  }
}

export class BrowserSpeechRecognitionAdapter implements SpeechInputPort {
  private recognition: RecognitionLike | null = null;

  isSupported(): boolean {
    return Boolean(recognitionConstructor());
  }

  start(callbacks: SpeechInputCallbacks): void {
    this.stop();
    const Constructor = recognitionConstructor();
    if (!Constructor) {
      callbacks.onError('unsupported', 'Speech recognition is unavailable in this browser.');
      callbacks.onEnd();
      return;
    }

    const recognition = new Constructor();
    this.recognition = recognition;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    recognition.onresult = (event) => {
      let interim = '';
      let final = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result?.[0]?.transcript || '';
        if (result?.isFinal) final += transcript;
        else interim += transcript;
      }
      if (interim.trim()) callbacks.onInterim(interim.trim());
      if (final.trim()) callbacks.onFinal(final.trim());
    };
    recognition.onerror = (event) => callbacks.onError(mapRecognitionError(event.error), event.message);
    recognition.onend = () => {
      if (this.recognition === recognition) this.recognition = null;
      callbacks.onEnd();
    };
    try {
      recognition.start();
    } catch (error) {
      this.recognition = null;
      callbacks.onError('unknown', error instanceof Error ? error.message : String(error));
      callbacks.onEnd();
    }
  }

  stop(): void {
    const recognition = this.recognition;
    this.recognition = null;
    if (!recognition) return;
    recognition.onresult = null;
    recognition.onerror = null;
    recognition.onend = null;
    try {
      recognition.abort?.();
    } catch {
      try { recognition.stop(); } catch { /* already stopped */ }
    }
  }
}

export class BrowserSpeechSynthesisAdapter implements SpeechOutputPort {
  private utterance: SpeechSynthesisUtterance | null = null;

  isSupported(): boolean {
    return 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined';
  }

  speak(text: string, callbacks: SpeechOutputCallbacks): void {
    this.stop();
    if (!this.isSupported()) {
      callbacks.onError('Speech synthesis is unavailable in this browser.');
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    this.utterance = utterance;
    utterance.rate = 1.02;
    utterance.pitch = 0.98;
    utterance.onstart = () => callbacks.onStart?.();
    utterance.onend = () => {
      if (this.utterance === utterance) this.utterance = null;
      callbacks.onEnd();
    };
    utterance.onerror = (event) => {
      if (this.utterance === utterance) this.utterance = null;
      callbacks.onError(event.error || 'speech-synthesis-error');
    };
    window.speechSynthesis.speak(utterance);
  }

  stop(): void {
    this.utterance = null;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  }
}
