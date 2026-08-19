import type {
  ConversationStreamClient,
  ServerConversationState,
  TurnEvent,
} from '../application/conversation';

function normalizeBaseUrl(value: string | undefined): string {
  return (value || '').replace(/\/$/, '');
}

function parseSseBlock(block: string): TurnEvent | null {
  const lines = block.split(/\r?\n/);
  let eventName = '';
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith('event:')) eventName = line.slice(6).trim();
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  const payload = JSON.parse(dataLines.join('\n')) as TurnEvent;
  if (eventName && payload.type !== eventName) {
    throw new Error(`SSE event mismatch: ${eventName} != ${payload.type}`);
  }
  return payload;
}

export class FetchSseConversationClient implements ConversationStreamClient {
  constructor(private readonly baseUrl = normalizeBaseUrl(import.meta.env.VITE_PORTFOLIO_API_URL)) {}

  async *streamTurn(input: {
    conversationId: string;
    question: string;
    signal?: AbortSignal;
  }): AsyncIterable<TurnEvent> {
    const url = `${this.baseUrl}/v1/conversations/${encodeURIComponent(input.conversationId)}/turns`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ question: input.question }),
      signal: input.signal,
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Portfolio API ${response.status}: ${detail || response.statusText}`);
    }
    if (!response.body) throw new Error('Portfolio API returned no SSE response body.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        let separator = buffer.search(/\r?\n\r?\n/);
        while (separator >= 0) {
          const block = buffer.slice(0, separator);
          const match = buffer.slice(separator).match(/^\r?\n\r?\n/);
          buffer = buffer.slice(separator + (match?.[0].length || 2));
          const event = parseSseBlock(block);
          if (event) yield event;
          separator = buffer.search(/\r?\n\r?\n/);
        }
        if (done) break;
      }
      if (buffer.trim()) {
        const event = parseSseBlock(buffer);
        if (event) yield event;
      }
    } finally {
      reader.releaseLock();
    }
  }

  async getState(conversationId: string): Promise<ServerConversationState> {
    const response = await fetch(
      `${this.baseUrl}/v1/conversations/${encodeURIComponent(conversationId)}/state`,
      { headers: { Accept: 'application/json' } },
    );
    if (!response.ok) throw new Error(`Portfolio API ${response.status}: ${response.statusText}`);
    return response.json() as Promise<ServerConversationState>;
  }
}

export const __test__ = { parseSseBlock };
