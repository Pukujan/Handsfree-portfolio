from handsfree_portfolio.adapters.neo4j_projection import Neo4jClaimProjectionAdapter


def test_projection_rejects_out_of_pack_event_before_provider_access() -> None:
    projection = Neo4jClaimProjectionAdapter(
        uri="bolt://127.0.0.1:1",
        user="neo4j",
        password="unused-test-password",
    )
    try:
        receipt = projection.apply_event(
            {
                "event_id": "evt_private_pack_rejected_0001",
                "event_type": "claim.proposed",
                "pack_id": "pack_private_not_mounted_1234",
                "recorded_at": "2026-08-19T20:00:00Z",
                "subject_refs": ["clm_private_0001"],
                "payload": {"claim_text": "private"},
            }
        )
    finally:
        projection.close()

    assert receipt.status == "failed"
    assert receipt.detail == "event is outside public pack"
