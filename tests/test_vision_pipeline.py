"""Focused tests for Phase 2 multimodal vision pipeline and condition mapping."""

import pytest
from fastapi.testclient import TestClient

from src.models.domain import AmazonCondition, Disposition, ObservedState, PartStatus, RecordStatus, Verdict
from src.vision.client import GeminiVisionClient, VisionPipelineResult
from src.vision.condition_mapper import map_condition
from src.vision.schemas import (
    CompletenessObservation,
    ConditionObservation,
    IdentityObservation,
    PartStatusObservation,
    VisionObservations,
)
from tests.conftest import VALID_1X1_JPEG_B64


def test_valid_multimodal_request(client: TestClient, sample_request_payload: dict):
    """Multimodal request with valid base64 image produces valid evidence record."""
    resp = client.post("/agent", json=sample_request_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["record_id"].startswith("RTN-")
    assert len(data["images"]) == 1
    assert data["images"][0]["filename"] == "UNIT-0003_1.jpg"
    assert data["images"][0]["size_bytes"] > 0
    assert len(data["checks"]) == 3

    # Check evidence citations match source image
    for c in data["checks"]:
        assert len(c["evidence"]) >= 1
        assert c["evidence"][0]["source"] == "UNIT-0003_1.jpg"

    assert data["outcome"]["disposition"] == "restock"
    assert data["outcome"]["amazon_condition"] == "Like New"
    assert data["content_hash"] is not None


def test_malformed_image_data_handled_safely(client: TestClient, sample_request_payload: dict):
    """Malformed base64 data must not crash the API (fails open to pending_review)."""
    payload = {
        **sample_request_payload,
        "images": [
            {
                "filename": "corrupted.jpg",
                "content_type": "image/jpeg",
                "data": "NOT_A_VALID_BASE64_STRING!@#$%",
            }
        ],
    }
    resp = client.post("/agent", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("pending", "review")
    assert data["outcome"]["disposition"] == "pending_review"


def test_missing_image_evidence(client: TestClient, sample_request_payload: dict):
    """Request with no photographs produces UNCERTAIN verdicts and pending_review."""
    payload = {**sample_request_payload, "images": []}
    resp = client.post("/agent", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["outcome"]["disposition"] == "pending_review"
    assert data["status"] == "pending"
    for c in data["checks"]:
        assert c["verdict"] == "UNCERTAIN"


def test_mocked_gemini_api_failure(client: TestClient, sample_request_payload: dict, monkeypatch):
    """When Gemini API times out or throws, system preserves record with pending_review."""
    def _mock_fail(self, ordered_sku, ordered_asin, parts_list, images):
        return VisionPipelineResult(
            success=False,
            observations=None,
            model_version="gemini-2.5-flash",
            latency_ms=150,
            error_message="Gemini 503 Service Unavailable / Gateway Timeout",
        )

    # Note: When success is False, client.analyze_return supplies fallback observations
    from src.vision.client import create_fallback_observations
    def _mock_fail_with_fallback(self, ordered_sku, ordered_asin, parts_list, images):
        return VisionPipelineResult(
            success=False,
            observations=create_fallback_observations(
                ordered_sku, ordered_asin, parts_list, "Gemini 503 Service Unavailable", "UNIT-0003_1.jpg"
            ),
            model_version="gemini-2.5-flash",
            latency_ms=150,
            error_message="Gemini 503 Service Unavailable",
        )

    monkeypatch.setattr(GeminiVisionClient, "analyze_return", _mock_fail_with_fallback)

    resp = client.post("/agent", json=sample_request_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["outcome"]["disposition"] == "pending_review"
    assert "Gemini 503 Service Unavailable" in data["outcome"]["rule_trace"]


def test_identity_uncertain_forces_review(client: TestClient, sample_request_payload: dict, monkeypatch):
    """Ambiguous or unreadable markings result in identity UNCERTAIN and pending_review."""
    def _mock_uncertain_id(self, ordered_sku, ordered_asin, parts_list, images):
        return VisionPipelineResult(
            success=True,
            observations=VisionObservations(
                identity=IdentityObservation(
                    verdict=Verdict.UNCERTAIN,
                    confidence=0.40,
                    claim="Product brand and model obscured by shipping sticker",
                    detail="Label obscured; barcode unscannable; unable to verify SKU.",
                    source_image="UNIT-0003_1.jpg",
                ),
                completeness=CompletenessObservation(
                    verdict=Verdict.PASS,
                    confidence=0.90,
                    claim="All parts present",
                    detail="Parts present",
                    parts=[],
                    source_image="UNIT-0003_1.jpg",
                ),
                condition=ConditionObservation(
                    observed_state=ObservedState.OPENED_UNUSED,
                    confidence=0.85,
                    claim="Pristine condition",
                    detail="Item appears unused",
                    source_image="UNIT-0003_1.jpg",
                ),
            ),
            model_version="gemini-2.5-flash (mock)",
            latency_ms=80,
        )

    monkeypatch.setattr(GeminiVisionClient, "analyze_return", _mock_uncertain_id)

    resp = client.post("/agent", json=sample_request_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"][0]["check_key"] == "identity"
    assert data["checks"][0]["verdict"] == "UNCERTAIN"
    assert data["outcome"]["disposition"] == "pending_review"


def test_completeness_part_statuses(client: TestClient, sample_request_payload: dict, monkeypatch):
    """Verify PRESENT, MISSING, and NOT_OBSERVED behave correctly."""
    # Case A: Missing required part -> completeness FAIL -> disposition refurbish/liquidate
    def _mock_missing_part(self, ordered_sku, ordered_asin, parts_list, images):
        return VisionPipelineResult(
            success=True,
            observations=VisionObservations(
                identity=IdentityObservation(
                    verdict=Verdict.PASS,
                    confidence=0.95,
                    claim="SKU matched",
                    detail="Matches SKU-PUZZLE-500",
                    source_image="UNIT-0003_1.jpg",
                ),
                completeness=CompletenessObservation(
                    verdict=Verdict.FAIL,
                    confidence=0.90,
                    claim="Missing poster accessory",
                    detail="Poster recess is visibly empty",
                    parts=[
                        PartStatusObservation(
                            part_name="puzzle pieces",
                            status=PartStatus.PRESENT,
                            confidence=0.95,
                            observation="Bag present",
                            source_image="UNIT-0003_1.jpg",
                        ),
                        PartStatusObservation(
                            part_name="poster",
                            status=PartStatus.MISSING,
                            confidence=0.90,
                            observation="Poster slot empty",
                            source_image="UNIT-0003_1.jpg",
                        ),
                    ],
                    source_image="UNIT-0003_1.jpg",
                ),
                condition=ConditionObservation(
                    observed_state=ObservedState.OPENED_UNUSED,
                    confidence=0.85,
                    claim="Like new item",
                    detail="Unused merchandise",
                    source_image="UNIT-0003_1.jpg",
                ),
            ),
            model_version="gemini-2.5-flash (mock)",
            latency_ms=85,
        )

    monkeypatch.setattr(GeminiVisionClient, "analyze_return", _mock_missing_part)
    resp = client.post("/agent", json=sample_request_payload)
    assert resp.status_code == 200
    data = resp.json()
    comp_check = next(c for c in data["checks"] if c["check_key"] == "completeness")
    assert comp_check["verdict"] == "FAIL"
    # Because condition is Like New but completeness is FAIL, disposition is refurbish (to replace missing part)
    assert data["outcome"]["disposition"] == "refurbish"

    # Case B: NOT_OBSERVED part -> completeness UNCERTAIN -> pending_review
    def _mock_not_observed_part(self, ordered_sku, ordered_asin, parts_list, images):
        return VisionPipelineResult(
            success=True,
            observations=VisionObservations(
                identity=IdentityObservation(
                    verdict=Verdict.PASS,
                    confidence=0.95,
                    claim="SKU matched",
                    detail="Matches SKU",
                    source_image="UNIT-0003_1.jpg",
                ),
                completeness=CompletenessObservation(
                    verdict=Verdict.UNCERTAIN,
                    confidence=0.60,
                    claim="Cannot determine if poster is inside sealed bag",
                    detail="Poster not observed in angle provided",
                    parts=[
                        PartStatusObservation(
                            part_name="puzzle pieces",
                            status=PartStatus.PRESENT,
                            confidence=0.95,
                            observation="Bag present",
                            source_image="UNIT-0003_1.jpg",
                        ),
                        PartStatusObservation(
                            part_name="poster",
                            status=PartStatus.NOT_OBSERVED,
                            confidence=0.50,
                            observation="Could be under pieces",
                            source_image="UNIT-0003_1.jpg",
                        ),
                    ],
                    source_image="UNIT-0003_1.jpg",
                ),
                condition=ConditionObservation(
                    observed_state=ObservedState.OPENED_UNUSED,
                    confidence=0.85,
                    claim="Like new",
                    detail="Unused",
                    source_image="UNIT-0003_1.jpg",
                ),
            ),
            model_version="gemini-2.5-flash (mock)",
            latency_ms=85,
        )

    monkeypatch.setattr(GeminiVisionClient, "analyze_return", _mock_not_observed_part)
    resp = client.post("/agent", json=sample_request_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"]["disposition"] == "pending_review"


def test_condition_uncertain(client: TestClient, sample_request_payload: dict, monkeypatch):
    """When condition is ambiguous or low confidence, system outputs UNCERTAIN and pending_review."""
    def _mock_uncertain_cond(self, ordered_sku, ordered_asin, parts_list, images):
        return VisionPipelineResult(
            success=True,
            observations=VisionObservations(
                identity=IdentityObservation(
                    verdict=Verdict.PASS,
                    confidence=0.95,
                    claim="SKU matched",
                    detail="Matches SKU",
                    source_image="UNIT-0003_1.jpg",
                ),
                completeness=CompletenessObservation(
                    verdict=Verdict.PASS,
                    confidence=0.95,
                    claim="All parts present",
                    detail="Complete",
                    parts=[],
                    source_image="UNIT-0003_1.jpg",
                ),
                condition=ConditionObservation(
                    observed_state=ObservedState.UNCERTAIN,
                    confidence=0.40,
                    claim="Condition cannot be assessed",
                    detail="Glare and distance prevent assessing item condition",
                    source_image="UNIT-0003_1.jpg",
                ),
            ),
            model_version="gemini-2.5-flash (mock)",
            latency_ms=90,
        )

    monkeypatch.setattr(GeminiVisionClient, "analyze_return", _mock_uncertain_cond)
    resp = client.post("/agent", json=sample_request_payload)
    assert resp.status_code == 200
    data = resp.json()
    cond_check = next(c for c in data["checks"] if c["check_key"] == "condition")
    assert cond_check["verdict"] == "UNCERTAIN"
    assert cond_check["amazon_condition"] == "UNCERTAIN"
    assert data["outcome"]["disposition"] == "pending_review"


def test_condition_mapping_rules():
    """Unit tests verifying conservative Amazon condition mapping."""
    # Factory sealed -> New
    obs_sealed = ConditionObservation(
        observed_state=ObservedState.FACTORY_SEALED,
        confidence=0.95,
        claim="Factory sealed",
        detail="Original shrink-wrap intact",
    )
    cond, verdict, conf, _ = map_condition(obs_sealed)
    assert cond == AmazonCondition.NEW
    assert verdict == Verdict.PASS

    # Opened unused -> Like New
    obs_opened = ConditionObservation(
        observed_state=ObservedState.OPENED_UNUSED,
        confidence=0.85,
        claim="Opened unused",
        detail="Open box, item pristine",
    )
    cond, verdict, conf, _ = map_condition(obs_opened)
    assert cond == AmazonCondition.LIKE_NEW
    assert verdict == Verdict.PASS

    # Signs of use (light scuffs) -> Very Good
    obs_used_light = ConditionObservation(
        observed_state=ObservedState.SIGNS_OF_USE,
        confidence=0.80,
        claim="Minor scuff",
        detail="Minor surface scuffs on corner",
    )
    cond, verdict, conf, _ = map_condition(obs_used_light)
    assert cond == AmazonCondition.VERY_GOOD
    assert verdict == Verdict.PASS

    # Signs of use (heavy wear) -> Acceptable
    obs_used_heavy = ConditionObservation(
        observed_state=ObservedState.SIGNS_OF_USE,
        confidence=0.80,
        claim="Heavy wear",
        detail="Significant scratches and wear across body",
    )
    cond, verdict, conf, _ = map_condition(obs_used_heavy)
    assert cond == AmazonCondition.ACCEPTABLE
    assert verdict == Verdict.PASS

    # Damaged (structural / cracked) -> Unacceptable
    obs_damaged = ConditionObservation(
        observed_state=ObservedState.DAMAGED,
        confidence=0.90,
        claim="Cracked case",
        detail="Heavy crack on casing, structural break",
    )
    cond, verdict, conf, _ = map_condition(obs_damaged)
    assert cond == AmazonCondition.UNACCEPTABLE
    assert verdict == Verdict.FAIL

    # Empty box -> Unacceptable
    obs_empty = ConditionObservation(
        observed_state=ObservedState.EMPTY_BOX,
        confidence=0.95,
        claim="Empty box",
        detail="Box is empty",
    )
    cond, verdict, conf, _ = map_condition(obs_empty)
    assert cond == AmazonCondition.UNACCEPTABLE
    assert verdict == Verdict.FAIL

    # Low confidence -> UNCERTAIN
    obs_low_conf = ConditionObservation(
        observed_state=ObservedState.FACTORY_SEALED,
        confidence=0.30,
        claim="Maybe sealed",
        detail="Too blurry to verify seal",
    )
    cond, verdict, conf, _ = map_condition(obs_low_conf)
    assert cond == AmazonCondition.UNCERTAIN
    assert verdict == Verdict.UNCERTAIN
