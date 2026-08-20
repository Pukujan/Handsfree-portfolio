from __future__ import annotations

from handsfree_portfolio.domain.knowledge import PublicClaimRecord
from handsfree_portfolio.domain.models import AnswerPlan, EvidenceRef, SupportedClaim
from handsfree_portfolio.domain.retrieval import RetrievalResult
from handsfree_portfolio.ports.interfaces import ClaimCatalogPort

SPOKEN_CLAIM_BUDGET = 1
EXPLICIT_PREMISE_MARKERS = (
    "i thought",
    "you said",
    "but you",
    "isn't",
    "isnt",
    "aren't",
    "arent",
    "doesn't that mean",
    "doesnt that mean",
    "so you're",
    "so you are",
    "actually",
)


def infer_subject(question: str, previous_subject: str | None) -> str | None:
    lowered = question.lower()
    if "fossil" in lowered:
        return "FOSSIL"
    if previous_subject == "FOSSIL" and ("neo4j" in lowered or "graph" in lowered or "it" in lowered or "that" in lowered):
        return "FOSSIL"
    return previous_subject


def update_referents(subject: str | None, previous: dict[str, str]) -> dict[str, str]:
    referents = dict(previous)
    if subject:
        referents.update({"it": subject, "that": subject, "this": subject})
    referents.setdefault("he", "Pujan")
    return referents


def explicit_premise_challenge(question: str) -> bool:
    lowered = question.strip().lower()
    return any(marker in lowered for marker in EXPLICIT_PREMISE_MARKERS)


def dialogue_act(question: str, subject: str | None, result: RetrievalResult) -> str:
    if result.abstained:
        return "ABSTAIN"
    lowered = question.strip().lower()
    if subject == "FOSSIL" and "neo4j" in lowered and explicit_premise_challenge(question):
        return "CORRECT_PREMISE"
    if lowered.startswith("why"):
        return "EXPLAIN"
    return "ANSWER_DIRECT"


def _record_to_claim(record: PublicClaimRecord) -> SupportedClaim:
    return SupportedClaim(
        claim_id=record.claim_id,
        proposition=record.proposition,
        support="supported",
        evidence_ids=record.evidence_ids,
    )


def build_answer_plan(
    *,
    catalog: ClaimCatalogPort,
    result: RetrievalResult,
    turn_id: str,
    generation: int,
    question: str,
    subject: str | None,
) -> AnswerPlan:
    if result.abstained:
        return AnswerPlan(
            turn_id=turn_id,
            generation=generation,
            dialogue_act="ABSTAIN",
            claims=(),
            evidence=(),
        )

    # Retrieval may keep multiple candidates for ranking/evidence drill-down, but the
    # first-contact spoken answer realizes only the highest-ranked supported claim.
    # This preserves retrieval behavior while keeping user-facing speech inside the
    # measured human response-length envelope.
    selected_claim_ids = result.claim_ids[:SPOKEN_CLAIM_BUDGET]
    records = tuple(catalog.get(claim_id) for claim_id in selected_claim_ids)
    evidence: list[EvidenceRef] = []
    seen_evidence: set[str] = set()
    for record in records:
        for evidence_id in record.evidence_ids:
            if evidence_id in seen_evidence:
                continue
            seen_evidence.add(evidence_id)
            evidence.append(
                EvidenceRef(
                    evidence_id=evidence_id,
                    source_ref=record.source_ref,
                    label=f"Evidence for {record.claim_id}",
                )
            )

    return AnswerPlan(
        turn_id=turn_id,
        generation=generation,
        dialogue_act=dialogue_act(question, subject, result),
        claims=tuple(_record_to_claim(record) for record in records),
        evidence=tuple(evidence),
    )
