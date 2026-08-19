export type SpeechInputErrorCode =
  | 'not-allowed'
  | 'audio-capture'
  | 'network'
  | 'no-speech'
  | 'aborted'
  | 'unsupported'
  | 'unknown';

export type SpeechInputCallbacks = {
  onInterim(text: string): void;
  onFinal(text: string): void;
  onError(code: SpeechInputErrorCode, detail?: string): void;
  onEnd(): void;
};

export interface SpeechInputPort {
  isSupported(): boolean;
  start(callbacks: SpeechInputCallbacks): void;
  stop(): void;
}

export type SpeechOutputCallbacks = {
  onStart?(): void;
  onEnd(): void;
  onError(detail?: string): void;
};

export interface SpeechOutputPort {
  isSupported(): boolean;
  speak(text: string, callbacks: SpeechOutputCallbacks): void;
  stop(): void;
}
