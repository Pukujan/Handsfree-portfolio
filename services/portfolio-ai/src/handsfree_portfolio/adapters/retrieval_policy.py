from __future__ import annotations

import json
from pathlib import Path

from handsfree_portfolio.application.retrieval import RetrievalPolicy, normalize_query


def load_retrieval_policy(path: Path) -> RetrievalPolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    exact = {
        normalize_query(question): tuple(str(claim_id) for claim_id in claim_ids)
        for question, claim_ids in payload["exactAliases"].items()
    }
    concepts = {
        str(claim_id): tuple(str(value) for value in values)
        for claim_id, values in payload["concepts"].items()
    }
    return RetrievalPolicy(exact_aliases=exact, concepts=concepts, top_k=int(payload.get("topK", 2)))


def should_graph_drilldown(path: Path, question: str) -> bool:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    normalized = normalize_query(question)
    return any(normalize_query(trigger) in normalized for trigger in payload["graphPolicy"]["evidenceDrilldownTriggers"])
