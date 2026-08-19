from fastapi.testclient import TestClient

from handsfree_portfolio.delivery.api import app


def test_health_and_fake_turn() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}

    response = client.post("/v1/turns", json={"question": "What is FOSSIL?", "generation": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["generation"] == 3
    assert payload["turnId"]
    assert payload["evidence"][0]["sourceRef"].startswith("fixture://portfolio-public/")
