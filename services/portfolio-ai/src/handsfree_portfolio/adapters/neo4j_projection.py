from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fossil_core.ports import ProjectionReceipt
from neo4j import GraphDatabase

from handsfree_portfolio.adapters.fossil_pack import PUBLIC_PACK_ID


class Neo4jClaimProjectionAdapter:
    """Deterministic, disposable Neo4j projection of accepted FOSSIL claim events.

    The adapter receives already-durable events. It has no event-store write path,
    never creates canonical claims, and never uses Neo4j internal IDs as semantic IDs.
    """

    name = "handsfree-neo4j-claim-projection"
    version = "1"
    projection_id = f"handsfree-public:{PUBLIC_PACK_ID}:v1"

    def __init__(self, *, uri: str, user: str, password: str) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    @staticmethod
    def _ordered_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(events, key=lambda event: (event["recorded_at"], event["event_id"]))

    def _record_event(self, session, event: dict[str, Any]) -> None:
        session.run(
            """
            MERGE (d:DurableEventProjection {projection_id: $projection_id, stable_id: $event_id})
            SET d.pack_id = $pack_id,
                d.event_type = $event_type,
                d.recorded_at = $recorded_at
            """,
            projection_id=self.projection_id,
            event_id=event["event_id"],
            pack_id=event["pack_id"],
            event_type=event["event_type"],
            recorded_at=event["recorded_at"],
        ).consume()

    def apply_event(self, event: dict[str, Any]) -> ProjectionReceipt:
        event_id = str(event["event_id"])
        if event.get("pack_id") != PUBLIC_PACK_ID:
            return ProjectionReceipt(self.name, self.version, event_id, "failed", "event is outside public pack")

        event_type = str(event["event_type"])
        try:
            with self.driver.session() as session:
                if event_type == "claim.proposed":
                    claim_id = str(event["subject_refs"][0])
                    session.run(
                        """
                        MERGE (c:PortfolioClaim {projection_id: $projection_id, stable_id: $claim_id})
                        SET c.pack_id = $pack_id,
                            c.claim_text = $claim_text,
                            c.state = 'proposed',
                            c.proposal_event_id = $event_id
                        """,
                        projection_id=self.projection_id,
                        claim_id=claim_id,
                        pack_id=PUBLIC_PACK_ID,
                        claim_text=str(event["payload"]["claim_text"]),
                        event_id=event_id,
                    ).consume()
                    for evidence_id in event.get("evidence_refs", []):
                        session.run(
                            """
                            MATCH (c:PortfolioClaim {projection_id: $projection_id, stable_id: $claim_id})
                            MERGE (e:EvidenceProjection {projection_id: $projection_id, stable_id: $stable_id})
                            SET e.pack_id = $pack_id
                            MERGE (c)-[:EVIDENCED_BY]->(e)
                            """,
                            projection_id=self.projection_id,
                            claim_id=claim_id,
                            stable_id=str(evidence_id),
                            pack_id=PUBLIC_PACK_ID,
                        ).consume()
                    for snapshot_id in event.get("source_snapshot_refs", []):
                        session.run(
                            """
                            MATCH (c:PortfolioClaim {projection_id: $projection_id, stable_id: $claim_id})
                            MERGE (s:SourceSnapshotProjection {projection_id: $projection_id, stable_id: $stable_id})
                            SET s.pack_id = $pack_id
                            MERGE (c)-[:SOURCED_FROM]->(s)
                            """,
                            projection_id=self.projection_id,
                            claim_id=claim_id,
                            stable_id=str(snapshot_id),
                            pack_id=PUBLIC_PACK_ID,
                        ).consume()
                    self._record_event(session, event)
                    return ProjectionReceipt(self.name, self.version, event_id, "applied")

                if event_type == "claim.state_changed":
                    claim_id = str(event["subject_refs"][0])
                    result = session.run(
                        """
                        MATCH (c:PortfolioClaim {projection_id: $projection_id, stable_id: $claim_id})
                        WHERE c.state = $from_state
                        SET c.state = $to_state,
                            c.state_event_id = $event_id
                        RETURN count(c) AS changed
                        """,
                        projection_id=self.projection_id,
                        claim_id=claim_id,
                        from_state=str(event["payload"].get("from_state")),
                        to_state=str(event["payload"]["to_state"]),
                        event_id=event_id,
                    ).single()
                    if result is None or int(result["changed"]) != 1:
                        return ProjectionReceipt(self.name, self.version, event_id, "failed", "claim state transition did not match projected state")
                    self._record_event(session, event)
                    return ProjectionReceipt(self.name, self.version, event_id, "applied")

                return ProjectionReceipt(self.name, self.version, event_id, "skipped", f"unsupported event type {event_type}")
        except Exception as exc:  # adapter boundary converts provider errors into receipts
            return ProjectionReceipt(self.name, self.version, event_id, "failed", f"{type(exc).__name__}: {exc}")

    def clear(self) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (n {projection_id: $projection_id}) DETACH DELETE n",
                projection_id=self.projection_id,
            ).consume()

    def rebuild(self, *, events_root: Path) -> list[ProjectionReceipt]:
        events = [json.loads(path.read_text(encoding="utf-8")) for path in Path(events_root).glob("*/*.json")]
        self.clear()
        return [self.apply_event(event) for event in self._ordered_events(events)]

    def health(self) -> dict[str, Any]:
        self.verify_connectivity()
        with self.driver.session() as session:
            record = session.run(
                "MATCH (n {projection_id: $projection_id}) RETURN count(n) AS count",
                projection_id=self.projection_id,
            ).single()
        return {"projection": self.name, "version": self.version, "status": "ok", "node_count": int(record["count"] if record else 0)}

    def semantic_snapshot(self) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            rows = session.run(
                """
                MATCH (c:PortfolioClaim {projection_id: $projection_id})
                OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(e:EvidenceProjection {projection_id: $projection_id})
                OPTIONAL MATCH (c)-[:SOURCED_FROM]->(s:SourceSnapshotProjection {projection_id: $projection_id})
                RETURN c.stable_id AS stable_id,
                       c.claim_text AS claim_text,
                       c.state AS state,
                       collect(DISTINCT e.stable_id) AS evidence_ids,
                       collect(DISTINCT s.stable_id) AS snapshot_ids
                ORDER BY stable_id
                """,
                projection_id=self.projection_id,
            )
            return [
                {
                    "stable_id": row["stable_id"],
                    "claim_text": row["claim_text"],
                    "state": row["state"],
                    "evidence_ids": sorted(value for value in row["evidence_ids"] if value is not None),
                    "snapshot_ids": sorted(value for value in row["snapshot_ids"] if value is not None),
                }
                for row in rows
            ]

    def semantic_digest(self) -> str:
        canonical = json.dumps(self.semantic_snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
