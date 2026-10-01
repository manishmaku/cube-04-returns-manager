"""Pytest fixtures for Returns Manager test suite."""

import os
import tempfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient

# Ensure test DB is used
_test_db_dir = tempfile.mkdtemp()
_test_db_path = str(Path(_test_db_dir) / "test_returns.db")
os.environ["DATABASE_PATH"] = _test_db_path
os.environ["ALLOWED_ORGS"] = "org_demo_alpha,org_demo_bravo"

from src.main import app
from src.models.domain import ObservedState, PartStatus, Verdict
from src.storage.database import init_db
from src.vision.client import GeminiVisionClient, VisionPipelineResult
from src.vision.schemas import (
    CompletenessObservation,
    ConditionObservation,
    IdentityObservation,
    PartStatusObservation,
    VisionObservations,
)

# Minimal valid 1x1 JPEG encoded in base64
VALID_1X1_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIs"
    "IxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAA"
    "AAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAk"
    "M2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKT"
    "lJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QA"
    "HwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdh"
    "cRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hp"
    "anN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk"
    "5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="
)


def mock_successful_vision_result(
    ordered_sku: str,
    ordered_asin: str,
    parts_list: list[str],
    images: list,
) -> VisionPipelineResult:
    """Helper creating a standard successful VisionPipelineResult."""
    source_img = images[0].filename if images else "UNIT-0003_1.jpg"
    return VisionPipelineResult(
        success=True,
        observations=VisionObservations(
            identity=IdentityObservation(
                verdict=Verdict.PASS,
                confidence=0.92,
                claim=f"Returned parcel contains SKU {ordered_sku}",
                detail=f"Returned item matches ordered SKU {ordered_sku} (ASIN: {ordered_asin}). Markings and physical design match reference catalogue.",
                source_image=source_img,
            ),
            completeness=CompletenessObservation(
                verdict=Verdict.PASS,
                confidence=0.88,
                claim="All expected parts and accessories verified present",
                detail=f"All {len(parts_list)} expected components verified present: {'; '.join(parts_list)}." if parts_list else "No accessories required.",
                parts=[
                    PartStatusObservation(
                        part_name=part,
                        status=PartStatus.PRESENT,
                        confidence=0.88,
                        observation="Verified present in parcel.",
                        source_image=source_img,
                    )
                    for part in parts_list
                ],
                source_image=source_img,
            ),
            condition=ConditionObservation(
                observed_state=ObservedState.OPENED_UNUSED,
                confidence=0.85,
                claim="Product condition satisfies Amazon Like New criteria",
                detail="Item package is opened but merchandise appears pristine and unused. Minor outer package shelf scuffing.",
                source_image=source_img,
            ),
        ),
        model_version="gemini-2.5-flash (mock)",
        latency_ms=95,
        error_message=None,
    )


@pytest.fixture(autouse=True)
def default_mock_vision(monkeypatch):
    """Mock GeminiVisionClient.analyze_return by default so tests run fast, offline, and deterministically."""
    def _mock_analyze(self, ordered_sku, ordered_asin, parts_list, images):
        return mock_successful_vision_result(ordered_sku, ordered_asin, parts_list, images)

    monkeypatch.setattr(GeminiVisionClient, "analyze_return", _mock_analyze)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initialize schema in the temporary test database."""
    init_db(_test_db_path)
    yield
    # Cleanup temp db
    if os.path.exists(_test_db_path):
        try:
            os.remove(_test_db_path)
        except OSError:
            pass


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Test client for FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_request_payload() -> dict:
    """Valid return assessment request payload matching returns_sample.csv data."""
    return {
        "organization_id": "org_demo_alpha",
        "client_id": "client_test",
        "unit_id": "UNIT-0003",
        "order_id": "ORD-DUMMY-50003",
        "ordered_sku": "SKU-PUZZLE-500",
        "ordered_asin": "B0DUMMY729",
        "parts_list": ["puzzle pieces", "poster"],
        "operator_id": "op_chen",
        "images": [
            {
                "filename": "UNIT-0003_1.jpg",
                "content_type": "image/jpeg",
                "data": VALID_1X1_JPEG_B64,
            }
        ],
    }
