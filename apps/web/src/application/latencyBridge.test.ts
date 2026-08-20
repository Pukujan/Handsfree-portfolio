import { describe, expect, it } from 'vitest';
import { DEFAULT_LATENCY_BRIDGE_MS, latencyBridgeFor } from './latencyBridge';

describe('latencyBridgeFor', () => {
  it('does not fabricate a bridge when no work is pending', () => {
    expect(latencyBridgeFor(DEFAULT_LATENCY_BRIDGE_MS + 5000, false)).toBeNull();
  });

  it('stays silent for fast pending work', () => {
    expect(latencyBridgeFor(DEFAULT_LATENCY_BRIDGE_MS - 1, true)).toBeNull();
  });

  it('permits one non-factual bridge after the real pending budget', () => {
    expect(latencyBridgeFor(DEFAULT_LATENCY_BRIDGE_MS, true)).toBe('Yeah — lemme check the public evidence.');
  });

  it('rejects nonsensical elapsed time', () => {
    expect(latencyBridgeFor(-1, true)).toBeNull();
    expect(latencyBridgeFor(Number.NaN, true)).toBeNull();
  });
});
