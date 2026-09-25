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
from src.storage.database import init_db


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
                "data": "dummy_base64_data",
            }
        ],
    }
