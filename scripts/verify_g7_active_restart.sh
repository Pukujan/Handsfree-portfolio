#!/usr/bin/env bash
set -euo pipefail

COMPOSE=(docker compose -f deploy/compose.production.yml)
ACTIVE_LOG=/tmp/g7-active-turn-restart.log

fail() {
  echo "--- active turn log ---"
  cat "$ACTIVE_LOG" 2>/dev/null || true
  echo "--- docker compose ps ---"
  "${COMPOSE[@]}" ps || true
  echo "--- docker compose logs ---"
  "${COMPOSE[@]}" logs --no-color || true
  exit 1
}

cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${COMPOSE[@]}" up -d
ready=false
for attempt in $(seq 1 30); do
  if curl -fsS http://localhost/health >/tmp/g7-active-health-before.json \
    && grep -q '"status":"ok"' /tmp/g7-active-health-before.json; then
    ready=true
    break
  fi
  sleep 1
done
test "$ready" = true || fail

(
  "${COMPOSE[@]}" exec -T api python -u - <<'PY'
import time

from handsfree_portfolio.delivery.composition import runtime_kernel


class DelayedRetriever:
    def __init__(self, delegate):
        self.delegate = delegate

    def retrieve(self, question):
        print("retriever.blocked", flush=True)
        time.sleep(60)
        return self.delegate.retrieve(question)


kernel = runtime_kernel()
kernel.response_cache = None
kernel.retriever = DelayedRetriever(kernel.retriever)
for event in kernel.stream_turn(
    conversation_id="g7-active-turn-restart",
    question="What is FOSSIL?",
):
    print(event.type, flush=True)
PY
) >"$ACTIVE_LOG" 2>&1 &
active_pid=$!

blocked=false
for attempt in $(seq 1 30); do
  if grep -q '^turn.accepted$' "$ACTIVE_LOG" 2>/dev/null \
    && grep -q '^retrieval.started$' "$ACTIVE_LOG" 2>/dev/null \
    && grep -q '^retriever.blocked$' "$ACTIVE_LOG" 2>/dev/null; then
    blocked=true
    break
  fi
  if ! kill -0 "$active_pid" 2>/dev/null; then
    break
  fi
  sleep 0.2
done
test "$blocked" = true || fail

"${COMPOSE[@]}" restart api
set +e
wait "$active_pid"
active_status=$?
set -e

# The in-flight process must have been terminated by the container restart.
test "$active_status" -ne 0 || fail
if grep -Eq '^(answer\.delta|answer\.grounded|turn\.complete)$' "$ACTIVE_LOG"; then
  fail
fi

ready=false
for attempt in $(seq 1 30); do
  if curl -fsS http://localhost/health >/tmp/g7-active-health-after.json \
    && grep -q '"status":"ok"' /tmp/g7-active-health-after.json; then
    ready=true
    break
  fi
  sleep 1
done
test "$ready" = true || fail

curl -fsS -N \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -H 'X-Request-ID: g7-active-restart-recovery' \
  --data '{"question":"What is FOSSIL?"}' \
  http://localhost/v1/conversations/g7-active-turn-after-restart/turns \
  >/tmp/g7-active-after-restart-sse.txt || fail

grep -q 'event: answer.grounded' /tmp/g7-active-after-restart-sse.txt || fail
grep -q 'event: turn.complete' /tmp/g7-active-after-restart-sse.txt || fail

printf '%s\n' '{"activeTurnReachedRetrieval":true,"inFlightProcessTerminatedByRestart":true,"staleAnswerPublishedAfterRestart":false,"freshGroundedTurnAfterRestart":true,"status":"PASS"}'
