"""Verification smoke test script for Returns Manager API."""

import json
from fastapi.testclient import TestClient
from src.main import app
from src.vision.client import GeminiVisionClient
from tests.conftest import VALID_1X1_JPEG_B64, mock_successful_vision_result


def main():
    # Inject standard mock for local offline smoke test
    original_analyze = GeminiVisionClient.analyze_return
    GeminiVisionClient.analyze_return = (
        lambda self, ordered_sku, ordered_asin, parts_list, images: mock_successful_vision_result(
            ordered_sku, ordered_asin, parts_list, images
        )
    )

    try:
        with TestClient(app) as client:
            # 1. Verify GET /health
            health_resp = client.get("/health")
            print(f"GET /health status: {health_resp.status_code}")
            print(f"GET /health body: {json.dumps(health_resp.json(), indent=2)}")
            assert health_resp.status_code == 200
            assert health_resp.json()["status"] == "healthy"

            # 2. Verify POST /agent with valid image payload
            payload = {
                "organization_id": "org_demo_alpha",
                "client_id": "client_001",
                "unit_id": "UNIT-0003",
                "order_id": "ORD-DUMMY-50003",
                "ordered_sku": "SKU-PUZZLE-500",
                "ordered_asin": "B0DUMMY729",
                "parts_list": ["puzzle pieces", "poster"],
                "operator_id": "op_chen",
                "images": [{"filename": "UNIT-0003_1.jpg", "content_type": "image/jpeg", "data": VALID_1X1_JPEG_B64}]
            }
            agent_resp = client.post("/agent", json=payload)
            print(f"POST /agent status: {agent_resp.status_code}")
            res = agent_resp.json()
            print(f"POST /agent record_id: {res['record_id']}")
            print(f"POST /agent status: {res['status']}")
            print(f"POST /agent content_hash: {res['content_hash']}")
            print(f"POST /agent checks count: {len(res['checks'])}")
            for c in res["checks"]:
                print(f"  Check [{c['check_key']}]: verdict={c['verdict']} confidence={c['confidence']} detail='{c['detail'][:50]}...'")
            print(f"POST /agent outcome: disposition={res['outcome']['disposition']} condition={res['outcome']['amazon_condition']}")
            assert agent_resp.status_code == 200
            assert res["record_id"].startswith("RTN-")
            assert len(res["checks"]) == 3
            assert res["outcome"]["disposition"] == "restock"

            # 3. Verify SQLite persistence and retrieval
            get_resp = client.get(f"/records/{res['record_id']}", params={"organization_id": "org_demo_alpha"})
            assert get_resp.status_code == 200
            print(f"GET /records/{res['record_id']} status: {get_resp.status_code} (Verified persistence)")

            print("\n>>> ALL SMOKE TEST VERIFICATIONS PASSED SUCCESSFULLY! <<<")
    finally:
        GeminiVisionClient.analyze_return = original_analyze


if __name__ == "__main__":
    main()
