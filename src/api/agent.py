"""Returns Manager Agent API endpoints (MOCK implementation for Phase 1)."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.config import ALLOWED_ORGS, GEMINI_MODEL
from src.models.domain import (
    Verdict,
    PartStatus,
    ObservedState,
    AmazonCondition,
    Disposition,
    RecordStatus,
)
from src.models.request import ReturnAssessmentRequest
from src.models.response import (
    EvidenceRecord,
    SubjectInfo,
    CheckResult,
    EvidenceItem,
    PartStatusItem,
    OutcomeResult,
    ImageRecord,
)
from src.storage.records_repo import (
    save_record,
    get_record,
    list_records,
)

router = APIRouter(tags=["Returns Manager Agent"])


def _compute_content_hash(data: dict) -> str:
    """Compute SHA-256 digest over canonical JSON representation."""
    canonical_bytes = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"


@router.post("/agent", response_model=EvidenceRecord, status_code=status.HTTP_200_OK)
async def process_return(request: ReturnAssessmentRequest) -> EvidenceRecord:
    """Process a returned item parcel and generate a structured evidence record.

    NOTE: Phase 1 provides a MOCK assessment pipeline conforming strictly to the
    official evidence contract. Real multimodal vision inference is scheduled for Phase 2+.
    """
    # Multi-tenant isolation check (RULES.md §2.1)
    if ALLOWED_ORGS and request.organization_id not in ALLOWED_ORGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unauthorized organization_id: '{request.organization_id}'. Allowed tenants: {ALLOWED_ORGS}",
        )

    now_utc = datetime.now(timezone.utc).isoformat()
    record_suffix = uuid.uuid4().hex[:6].upper()
    record_id = f"RTN-{request.unit_id.replace('UNIT-', '')}-{record_suffix}"

    # Prepare image metadata records
    image_records = [
        ImageRecord(
            image_id=f"img_{i+1:03d}",
            filename=img.filename,
            storage_path=f"{request.organization_id}/{request.unit_id}/{img.filename}",
            content_type=img.content_type or "image/jpeg",
            size_bytes=len(img.data.encode("utf-8")) if img.data else 0,
            hash_sha256=hashlib.sha256(img.filename.encode("utf-8")).hexdigest(),
        )
        for i, img in enumerate(request.images)
    ]

    # MOCK Check 1: Identity
    identity_check = CheckResult(
        check_key="identity",
        verdict=Verdict.PASS,
        confidence=0.92,
        detail=f"Returned item matches ordered SKU {request.ordered_sku} (ASIN: {request.ordered_asin}). Markings and physical design match reference catalogue.",
        evidence=[
            EvidenceItem(
                evidence_id="ev_id_001",
                claim=f"Returned parcel contains SKU {request.ordered_sku}",
                evidence_type="visual_match",
                source=image_records[0].filename if image_records else "inspection_camera_1",
                observation="Brand typography and SKU label match catalogue reference specifications.",
                confidence=0.92,
            )
        ],
        model_version=f"{GEMINI_MODEL} (mock)",
        latency_ms=120,
    )

    # MOCK Check 2: Completeness
    parts_status_items = [
        PartStatusItem(part=part, status=PartStatus.PRESENT, confidence=0.88)
        for part in request.parts_list
    ]
    parts_detail = (
        f"All {len(request.parts_list)} expected components verified present: {'; '.join(request.parts_list)}."
        if request.parts_list
        else "No expected accessories specified in catalogue."
    )
    completeness_check = CheckResult(
        check_key="completeness",
        verdict=Verdict.PASS,
        confidence=0.88,
        detail=parts_detail,
        evidence=[
            EvidenceItem(
                evidence_id="ev_comp_001",
                claim="Expected parts and accessories present in package",
                evidence_type="visual_observation",
                source=image_records[0].filename if image_records else "inspection_camera_1",
                observation="All required accessories identified and accounted for in parcel inspection photo.",
                confidence=0.88,
            )
        ],
        parts_status=parts_status_items,
        model_version=f"{GEMINI_MODEL} (mock)",
        latency_ms=95,
    )

    # MOCK Check 3: Condition (using Amazon's published condition scale)
    condition_check = CheckResult(
        check_key="condition",
        verdict=Verdict.PASS,
        confidence=0.85,
        detail="Item package is opened but merchandise appears pristine and unused. Minor outer package shelf scuffing.",
        evidence=[
            EvidenceItem(
                evidence_id="ev_cond_001",
                claim="Product condition satisfies Amazon Like New criteria",
                evidence_type="visual_assessment",
                source=image_records[0].filename if image_records else "inspection_camera_1",
                observation="Packaging opened; contents pristine with no signs of wear, stains, or functional damage.",
                confidence=0.85,
            )
        ],
        observed_state=ObservedState.OPENED_UNUSED,
        amazon_condition=AmazonCondition.LIKE_NEW,
        model_version=f"{GEMINI_MODEL} (mock)",
        latency_ms=110,
    )

    outcome = OutcomeResult(
        disposition=Disposition.RESTOCK,
        amazon_condition=AmazonCondition.LIKE_NEW,
        rule_trace="identity=PASS ∧ completeness=PASS ∧ condition=LikeNew → restock (Rule R05)",
        confidence=0.85,
    )

    subject = SubjectInfo(
        unit_id=request.unit_id,
        order_id=request.order_id,
        ordered_sku=request.ordered_sku,
        ordered_asin=request.ordered_asin,
    )

    evidence_record = EvidenceRecord(
        record_id=record_id,
        schema_version="1.0.0",
        organization_id=request.organization_id,
        client_id=request.client_id,
        agent="returns-manager@1.0.0",
        subject=subject,
        captured_at=now_utc,
        operator_label=request.operator_id,
        images=image_records,
        checks=[identity_check, completeness_check, condition_check],
        outcome=outcome,
        overrides=[],
        status=RecordStatus.COMPLETED,
        content_hash=None,
    )

    # Compute content hash over the record payload (excluding content_hash itself)
    record_dict = evidence_record.model_dump(mode="json", exclude={"content_hash"})
    evidence_record.content_hash = _compute_content_hash(record_dict)

    # Save to tenant-isolated SQLite storage
    save_record(evidence_record)

    return evidence_record


@router.get("/records/{record_id}", response_model=EvidenceRecord)
async def get_evidence_record(
    record_id: str,
    organization_id: str = Query(..., description="Tenant organization ID enforcing isolation"),
) -> EvidenceRecord:
    """Retrieve an evidence record by ID, scoped to the caller's tenant."""
    record = get_record(record_id, organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Record '{record_id}' not found for organization '{organization_id}'.",
        )
    return record


@router.get("/records", response_model=list[EvidenceRecord])
async def list_evidence_records(
    organization_id: str = Query(..., description="Tenant organization ID enforcing isolation"),
    unit_id: Optional[str] = Query(None, description="Optional unit_id filter"),
    status_filter: Optional[str] = Query(None, alias="status", description="Optional status filter"),
) -> list[EvidenceRecord]:
    """List all evidence records belonging strictly to the specified tenant."""
    return list_records(organization_id, unit_id=unit_id, status=status_filter)
