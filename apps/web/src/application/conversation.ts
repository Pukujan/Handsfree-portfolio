export type ConversationState =
  | 'idle'
  | 'listening'
  | 'retrieving'
  | 'rendering'
  | 'speaking'
  | 'interrupted'
  | 'complete'
  | 'cancelled'
  | 'error'
  | 'fallback';

export type TurnEventType =
  | 'turn.accepted'
  | 'retrieval.started'
  | 'evidence.found'
  | 'answer.planned'
  | 'answer.delta'
  | 'answer.grounded'
  | 'turn.complete'
  | 'turn.cancelled';

export type TurnEvent = {
  contractVersion: '1.0.0';
  turnId: string;
  generation: number;
  type: TurnEventType;
  occurredAt: string;
  payload: Record<string, unknown>;
};

export type ServerConversationState = {
  contractVersion: '1.0.0';
  activeGeneration: number;
  state: ConversationState;
  activeSubject: string | null;
  referents: Record<string, string>;
};

export interface ConversationStreamClient {
  streamTurn(input: {
    conversationId: string;
    question: string;
    signal?: AbortSignal;
  }): AsyncIterable<TurnEvent>;
  getState(conversationId: string): Promise<ServerConversationState>;
}
