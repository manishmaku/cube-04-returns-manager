"""Tests for domain, request, and evidence contract models."""

import pytest
from pydantic import ValidationError

from src.models.domain import (
    Verdict,
    PartStatus,
    ObservedState,
    AmazonCondition,
    Disposition,
    RecordStatus,
)
from src.models.request import ReturnAssessmentRequest, ImageInputItem
from src.models.response import (
    EvidenceRecord,
    SubjectInfo,
    CheckResult,
    OutcomeResult,
    EvidenceItem,
    PartStatusItem,
)


def test_verdict_enums_include_uncertain():
    """RULES.md §2.4: UNCERTAIN must be a first-class verdict."""
    assert Verdict.PASS == "PASS"
    assert Verdict.FAIL == "FAIL"
    assert Verdict.UNCERTAIN == "UNCERTAIN"


def test_part_status_enums():
    """Completeness check requires PRESENT, MISSING, NOT_OBSERVED."""
    assert PartStatus.PRESENT == "PRESENT"
    assert PartStatus.MISSING == "MISSING"
    assert PartStatus.NOT_OBSERVED == "NOT_OBSERVED"


def test_amazon_condition_scale():
    """RULES.md §4: Official Amazon condition scale must be preserved."""
    assert AmazonCondition.NEW == "New"
    assert AmazonCondition.LIKE_NEW == "Like New"
    assert AmazonCondition.VERY_GOOD == "Very Good"
    assert AmazonCondition.GOOD == "Good"
    assert AmazonCondition.ACCEPTABLE == "Acceptable"
    assert AmazonCondition.UNACCEPTABLE == "Unacceptable"
    assert AmazonCondition.UNCERTAIN == "UNCERTAIN"


def test_disposition_enums():
    """RULES.md §4: All required disposition actions must be supported."""
    assert Disposition.RESTOCK == "restock"
    assert Disposition.REFURBISH == "refurbish"
    assert Disposition.LIQUIDATE == "liquidate"
    assert Disposition.DISPOSE == "dispose"
    assert Disposition.PENDING_REVIEW == "pending_review"


def test_return_assessment_request_validation():
    """ReturnAssessmentRequest validates required fields."""
    req = ReturnAssessmentRequest(
        organization_id="org_demo_alpha",
        unit_id="UNIT-0003",
        order_id="ORD-001",
        ordered_sku="SKU-1",
        ordered_asin="B001",
        parts_list=["part_a", "part_b"],
        images=[ImageInputItem(filename="img1.jpg")],
    )
    assert req.organization_id == "org_demo_alpha"
    assert len(req.parts_list) == 2
    assert len(req.images) == 1


def test_return_assessment_request_missing_required_fields():
    """Missing required fields raises ValidationError."""
    with pytest.raises(ValidationError):
        ReturnAssessmentRequest(
            organization_id="org_demo_alpha",
            # missing unit_id, order_id, ordered_sku, ordered_asin
        )


def test_evidence_record_structure():
    """EvidenceRecord strictly adheres to the official Buildathon schema."""
    record = EvidenceRecord(
        record_id="RTN-0001",
        schema_version="1.0.0",
        organization_id="org_demo_alpha",
        agent="returns-manager@1.0.0",
        subject=SubjectInfo(
            unit_id="UNIT-0001",
            order_id="ORD-100",
            ordered_sku="SKU-TEST",
            ordered_asin="B0TEST",
        ),
        captured_at="2026-09-25T12:00:00Z",
        checks=[
            CheckResult(
                check_key="identity",
                verdict=Verdict.UNCERTAIN,
                confidence=0.45,
                detail="Label blurry, inconclusive visual evidence.",
                evidence=[
                    EvidenceItem(
                        evidence_id="ev_01",
                        claim="Item match",
                        evidence_type="visual_match",
                        source="img1.jpg",
                        observation="Barcode partially obscured",
                        confidence=0.45,
                    )
                ],
            )
        ],
        outcome=OutcomeResult(
            disposition=Disposition.PENDING_REVIEW,
            amazon_condition=AmazonCondition.UNCERTAIN,
            rule_trace="identity=UNCERTAIN → pending_review (Rule R02)",
            confidence=0.45,
        ),
        status=RecordStatus.PENDING,
        content_hash="sha256:abc123",
    )
    dumped = record.model_dump(mode="json")
    assert dumped["record_id"] == "RTN-0001"
    assert dumped["checks"][0]["verdict"] == "UNCERTAIN"
    assert dumped["outcome"]["disposition"] == "pending_review"
    assert dumped["status"] == "pending"
