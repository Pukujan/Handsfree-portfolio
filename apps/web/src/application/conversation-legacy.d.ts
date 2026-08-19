import './conversation';

declare module './conversation' {
  export interface EvidenceRef {
    evidenceId: string;
    label: string;
    sourceRef: string;
  }

  export interface ConversationAnswer {
    turnId: string;
    generation: number;
    text: string;
    evidence: EvidenceRef[];
  }

  /** @deprecated G0 deterministic fixture surface; production uses ConversationStreamClient. */
  export interface ConversationClient {
    ask(input: { question: string; generation: number }): Promise<ConversationAnswer>;
  }
}
