export const DEFAULT_LATENCY_BRIDGE_MS = 1400;

export function latencyBridgeFor(
  elapsedMs: number,
  workPending: boolean,
  thresholdMs = DEFAULT_LATENCY_BRIDGE_MS,
): string | null {
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) return null;
  if (!workPending || elapsedMs < thresholdMs) return null;
  return 'Yeah — lemme check the public evidence.';
}
