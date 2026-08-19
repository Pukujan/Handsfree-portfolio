import { describe, expect, it } from 'vitest';
import { __test__ } from './fetchSseConversationClient';

describe('fetch SSE event parsing', () => {
  it('parses a verified turn event block', () => {
    const result = __test__.parseSseBlock(
      'event: retrieval.started\n' +
      'data: {"contractVersion":"1.0.0","turnId":"t1","generation":1,"type":"retrieval.started","occurredAt":"2026-08-19T21:00:00Z","payload":{}}',
    );
    expect(result?.type).toBe('retrieval.started');
    expect(result?.generation).toBe(1);
  });

  it('rejects a mismatched SSE event name and JSON contract type', () => {
    expect(() => __test__.parseSseBlock(
      'event: answer.grounded\n' +
      'data: {"contractVersion":"1.0.0","turnId":"t1","generation":1,"type":"answer.delta","occurredAt":"2026-08-19T21:00:00Z","payload":{}}',
    )).toThrow(/event mismatch/i);
  });
});
