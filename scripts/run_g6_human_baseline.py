from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator
from uuid import uuid4

import httpx

FROZEN_CANDIDATE_REVISION = "6174cc886aff82a4cfa3ae4f64ac79cfbf98b15d"
BASELINE_PROTOCOL_VERSION = "1.0.0"
SHA40 = re.compile(r"^[a-f0-9]{40}$")


class BaselineProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class BaselineResult:
    itemId: str
    questionSha256: str
    baselineProtocolVersion: str
    baselineRevision: str
    candidateRevision: str
    conversationId: str
    answer: str


def fresh_conversation_id() -> str:
    return f"g6-baseline-{uuid4()}"


def iter_sse_events(lines: Iterable[str]) -> Iterator[dict]:
    event_name = ""
    data_lines: list[str] = []

    def decode() -> dict | None:
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = ""
            return None
        event = json.loads("\n".join(data_lines))
        if event_name and event.get("type") != event_name:
            raise BaselineProtocolError(
                f"SSE event mismatch: {event_name} != {event.get('type')}"
            )
        event_name = ""
        data_lines = []
        return event

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            event = decode()
            if event is not None:
                yield event
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    event = decode()
    if event is not None:
        yield event


def collect_grounded_answer(events: Iterable[dict]) -> str:
    deltas: list[str] = []
    grounded = False
    complete = False

    for event in events:
        event_type = event.get("type")
        payload = event.get("payload") or {}
        if event_type == "turn.cancelled":
            raise BaselineProtocolError(
                f"candidate turn cancelled: {payload.get('reason', 'unknown')}"
            )
        if event_type == "answer.delta":
            text = payload.get("text")
            if not isinstance(text, str) or not text:
                raise BaselineProtocolError("answer.delta did not contain text")
            deltas.append(text)
        elif event_type == "answer.grounded":
            grounded = True
        elif event_type == "turn.complete":
            complete = True

    if not deltas:
        raise BaselineProtocolError("candidate stream contained no answer text")
    if not grounded:
        raise BaselineProtocolError("candidate stream never emitted answer.grounded")
    if not complete:
        raise BaselineProtocolError("candidate stream never emitted turn.complete")
    return "".join(deltas)


def run_baseline_turn(
    *,
    client: httpx.Client,
    api_url: str,
    item_id: str,
    question: str,
    baseline_revision: str,
) -> BaselineResult:
    if not item_id.strip():
        raise BaselineProtocolError("itemId must not be blank")
    if not question.strip():
        raise BaselineProtocolError("question must not be blank")
    if not SHA40.fullmatch(baseline_revision):
        raise BaselineProtocolError("baselineRevision must be a 40-character git SHA")

    conversation_id = fresh_conversation_id()
    endpoint = (
        f"{api_url.rstrip('/')}/v1/conversations/"
        f"{conversation_id}/turns"
    )
    with client.stream(
        "POST",
        endpoint,
        headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
        json={"question": question},
    ) as response:
        response.raise_for_status()
        answer = collect_grounded_answer(iter_sse_events(response.iter_lines()))

    return BaselineResult(
        itemId=item_id,
        questionSha256=hashlib.sha256(question.encode("utf-8")).hexdigest(),
        baselineProtocolVersion=BASELINE_PROTOCOL_VERSION,
        baselineRevision=baseline_revision,
        candidateRevision=FROZEN_CANDIDATE_REVISION,
        conversationId=conversation_id,
        answer=answer,
    )


def iter_items(path: Path) -> Iterator[tuple[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            item = json.loads(raw_line)
            item_id = item.get("itemId")
            question = item.get("question")
            if not isinstance(item_id, str) or not isinstance(question, str):
                raise BaselineProtocolError(
                    f"input line {line_number} requires string itemId and question"
                )
            yield item_id, question


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen G6 simple-text baseline against the candidate API."
    )
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--input", type=Path, required=True, help="private JSONL input")
    parser.add_argument("--output", type=Path, required=True, help="private JSONL output")
    parser.add_argument("--baseline-revision", required=True)
    args = parser.parse_args()

    results: list[BaselineResult] = []
    with httpx.Client(timeout=30.0) as client:
        for item_id, question in iter_items(args.input):
            results.append(
                run_baseline_turn(
                    client=client,
                    api_url=args.api_url,
                    item_id=item_id,
                    question=question,
                    baseline_revision=args.baseline_revision,
                )
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(asdict(result), sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
