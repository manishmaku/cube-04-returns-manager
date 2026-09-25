"""Tests for POST /agent MOCK endpoint and record persistence."""

from fastapi.testclient import TestClient


def test_post_agent_mock_returns_expected_structure(
    client: TestClient,
    sample_request_payload: dict,
):
    """POST /agent must return a valid evidence record conforming to official schema."""
    response = client.post("/agent", json=sample_request_payload)
    assert response.status_code == 200

    data = response.json()
    assert "record_id" in data
    assert data["record_id"].startswith("RTN-")
    assert data["schema_version"] == "1.0.0"
    assert data["organization_id"] == "org_demo_alpha"
    assert data["agent"] == "returns-manager@1.0.0"
    assert data["status"] == "completed"
    assert data["content_hash"] is not None
    assert data["content_hash"].startswith("sha256:")

    # Verify subject
    subject = data["subject"]
    assert subject["unit_id"] == "UNIT-0003"
    assert subject["order_id"] == "ORD-DUMMY-50003"
    assert subject["ordered_sku"] == "SKU-PUZZLE-500"
    assert subject["ordered_asin"] == "B0DUMMY729"

    # Verify checks
    checks = data["checks"]
    assert len(checks) == 3
    check_keys = {c["check_key"] for c in checks}
    assert check_keys == {"identity", "completeness", "condition"}

    for c in checks:
        assert c["verdict"] in ("PASS", "FAIL", "UNCERTAIN")
        assert 0.0 <= c["confidence"] <= 1.0
        assert len(c["detail"]) > 0
        assert len(c["evidence"]) >= 1
        assert "ev_" in c["evidence"][0]["evidence_id"]

    # Completeness check includes parts breakdown
    comp_check = next(c for c in checks if c["check_key"] == "completeness")
    assert comp_check["parts_status"] is not None
    parts = {p["part"]: p["status"] for p in comp_check["parts_status"]}
    assert "puzzle pieces" in parts
    assert "poster" in parts

    # Condition check includes observed_state and amazon_condition
    cond_check = next(c for c in checks if c["check_key"] == "condition")
    assert cond_check["observed_state"] == "opened_unused"
    assert cond_check["amazon_condition"] == "Like New"

    # Outcome
    outcome = data["outcome"]
    assert outcome["disposition"] == "restock"
    assert outcome["amazon_condition"] == "Like New"
    assert "rule_trace" in outcome


def test_post_agent_persists_and_retrievable(
    client: TestClient,
    sample_request_payload: dict,
):
    """A record created via POST /agent must be retrievable via GET /records/{id}."""
    create_resp = client.post("/agent", json=sample_request_payload)
    assert create_resp.status_code == 200
    record_id = create_resp.json()["record_id"]

    get_resp = client.get(
        f"/records/{record_id}",
        params={"organization_id": "org_demo_alpha"},
    )
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["record_id"] == record_id
    assert fetched["organization_id"] == "org_demo_alpha"
