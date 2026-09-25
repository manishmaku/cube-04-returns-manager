"""Tests for Multi-tenant data isolation (RULES.md §2.1)."""

from fastapi.testclient import TestClient


def test_cross_tenant_record_access_denied(client: TestClient, sample_request_payload: dict):
    """An organization cannot access another organization's records (returns 404)."""
    # Create record for org_demo_alpha
    alpha_payload = {**sample_request_payload, "organization_id": "org_demo_alpha", "unit_id": "UNIT-ALPHA-01"}
    resp = client.post("/agent", json=alpha_payload)
    assert resp.status_code == 200
    record_id = resp.json()["record_id"]

    # org_demo_alpha CAN retrieve its own record
    alpha_fetch = client.get(f"/records/{record_id}", params={"organization_id": "org_demo_alpha"})
    assert alpha_fetch.status_code == 200
    assert alpha_fetch.json()["organization_id"] == "org_demo_alpha"

    # org_demo_bravo CANNOT retrieve org_demo_alpha's record
    bravo_fetch = client.get(f"/records/{record_id}", params={"organization_id": "org_demo_bravo"})
    assert bravo_fetch.status_code == 404


def test_cross_tenant_listing_isolation(client: TestClient, sample_request_payload: dict):
    """Querying records as org_demo_bravo must see ZERO rows belonging to org_demo_alpha."""
    # Create a record for alpha
    alpha_payload = {**sample_request_payload, "organization_id": "org_demo_alpha", "unit_id": "UNIT-ALPHA-02"}
    client.post("/agent", json=alpha_payload)

    # List as bravo
    bravo_list = client.get("/records", params={"organization_id": "org_demo_bravo"})
    assert bravo_list.status_code == 200
    records = bravo_list.json()
    for rec in records:
        assert rec["organization_id"] == "org_demo_bravo"
        assert rec["organization_id"] != "org_demo_alpha"


def test_unauthorized_tenant_rejected(client: TestClient, sample_request_payload: dict):
    """An unauthorized organization ID must be rejected at the API boundary."""
    bad_payload = {**sample_request_payload, "organization_id": "org_unauthorized_intruder"}
    resp = client.post("/agent", json=bad_payload)
    assert resp.status_code == 400
    assert "Invalid or unauthorized organization_id" in resp.json()["detail"]
