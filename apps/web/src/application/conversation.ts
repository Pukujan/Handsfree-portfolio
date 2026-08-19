export type ConversationState =
  | 'idle'
  | 'listening'
  | 'retrieving'
  | 'speaking'
  | 'interrupted'
  | 'error'
  | 'fallback';

export type EvidenceRef = {
  evidenceId: string;
  label: string;
  sourceRef: string;
};

export type ConversationAnswer = {
  turnId: string;
  generation: number;
  text: string;
  evidence: EvidenceRef[];
};

export interface ConversationClient {
  ask(input: { question: string; generation: number }): Promise<ConversationAnswer>;
}
