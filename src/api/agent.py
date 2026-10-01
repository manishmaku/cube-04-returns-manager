"""Returns Manager Agent API endpoints integrated with Gemini multimodal vision pipeline."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.config import ALLOWED_ORGS
from src.models.domain import (
    AmazonCondition,
    Disposition,
    PartStatus,
    RecordStatus,
    Verdict,
)
from src.models.request import ReturnAssessmentRequest
from src.models.response import (
    CheckResult,
    EvidenceItem,
    EvidenceRecord,
    ImageRecord,
    OutcomeResult,
    PartStatusItem,
    SubjectInfo,
)
from src.storage.records_repo import (
    get_record,
    list_records,
    save_record,
)
from src.vision.client import GeminiVisionClient
from src.vision.condition_mapper import map_condition
from src.vision.image_utils import validate_images

router = APIRouter(tags=["Returns Manager Agent"])

# Vision client instance (lazy init on first call)
_vision_client: Optional[GeminiVisionClient] = None


def get_vision_client() -> GeminiVisionClient:
    """Get or create singleton vision client."""
    global _vision_client
    if _vision_client is None:
        _vision_client = GeminiVisionClient()
    return _vision_client


def _compute_content_hash(data: dict) -> str:
    """Compute SHA-256 digest over canonical JSON representation."""
    canonical_bytes = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"


@router.post("/agent", response_model=EvidenceRecord, status_code=status.HTTP_200_OK)
async def process_return(request: ReturnAssessmentRequest) -> EvidenceRecord:
    """Process a returned item parcel and generate a structured evidence record.

    Executes:
    1. Multi-tenant isolation verification
    2. Image validation and safe base64 decoding
    3. Multimodal visual inspection via Gemini 2.5 Flash
    4. Deterministic condition mapping (Amazon condition scale)
    5. Deterministic rule-based disposition recommendation
    6. Tamper-evident content hash generation & SQLite persistence
    """
    # 1. Multi-tenant isolation check (RULES.md §2.1)
    if ALLOWED_ORGS and request.organization_id not in ALLOWED_ORGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unauthorized organization_id: '{request.organization_id}'. Allowed tenants: {ALLOWED_ORGS}",
        )

    now_utc = datetime.now(timezone.utc).isoformat()
    record_suffix = uuid.uuid4().hex[:6].upper()
    record_id = f"RTN-{request.unit_id.replace('UNIT-', '')}-{record_suffix}"

    # 2. Image validation
    valid_images, image_errors = validate_images(request.images)

    image_records = [
        ImageRecord(
            image_id=f"img_{i+1:03d}",
            filename=img.filename,
            storage_path=f"{request.organization_id}/{request.unit_id}/{img.filename}",
            content_type=img.mime_type,
            size_bytes=img.size_bytes,
            hash_sha256=hashlib.sha256(img.data).hexdigest(),
        )
        for i, img in enumerate(valid_images)
    ]

    # 3. Vision Analysis
    vision_client = get_vision_client()
    if not valid_images:
        err_reason = "; ".join(image_errors) if image_errors else "No photographic evidence provided for assessment."
        from src.vision.client import create_fallback_observations, VisionPipelineResult
        fallback_obs = create_fallback_observations(
            ordered_sku=request.ordered_sku,
            ordered_asin=request.ordered_asin,
            parts_list=request.parts_list,
            reason=err_reason,
            primary_image="no_valid_image",
        )
        vision_result = VisionPipelineResult(
            success=False,
            observations=fallback_obs,
            model_version=vision_client.model_name,
            latency_ms=0,
            error_message=err_reason,
        )
    else:
        vision_result = vision_client.analyze_return(
            ordered_sku=request.ordered_sku,
            ordered_asin=request.ordered_asin,
            parts_list=request.parts_list,
            images=valid_images,
        )

    obs = vision_result.observations

    # Build Check 1: Identity
    identity_evidence = [
        EvidenceItem(
            evidence_id=f"ev_id_{record_suffix}",
            claim=obs.identity.claim,
            evidence_type="visual_match",
            source=obs.identity.source_image,
            observation=obs.identity.detail,
            confidence=obs.identity.confidence,
        )
    ]
    identity_check = CheckResult(
        check_key="identity",
        verdict=obs.identity.verdict,
        confidence=obs.identity.confidence,
        detail=obs.identity.detail,
        evidence=identity_evidence,
        model_version=vision_result.model_version,
        latency_ms=vision_result.latency_ms,
    )

    # Build Check 2: Completeness
    parts_status_items = [
        PartStatusItem(
            part=p.part_name,
            status=p.status,
            confidence=p.confidence,
        )
        for p in obs.completeness.parts
    ]
    comp_evidence = [
        EvidenceItem(
            evidence_id=f"ev_comp_{record_suffix}",
            claim=obs.completeness.claim,
            evidence_type="visual_observation",
            source=obs.completeness.source_image,
            observation=obs.completeness.detail,
            confidence=obs.completeness.confidence,
        )
    ]
    completeness_check = CheckResult(
        check_key="completeness",
        verdict=obs.completeness.verdict,
        confidence=obs.completeness.confidence,
        detail=obs.completeness.detail,
        evidence=comp_evidence,
        parts_status=parts_status_items,
        model_version=vision_result.model_version,
        latency_ms=0,
    )

    # Build Check 3: Condition (Deterministic mapping to Amazon condition scale)
    amazon_cond, cond_verdict, cond_conf, cond_rule = map_condition(obs.condition)
    cond_evidence = [
        EvidenceItem(
            evidence_id=f"ev_cond_{record_suffix}",
            claim=obs.condition.claim,
            evidence_type="visual_assessment",
            source=obs.condition.source_image,
            observation=f"{obs.condition.detail} [Classification: {cond_rule}]",
            confidence=cond_conf,
        )
    ]
    condition_check = CheckResult(
        check_key="condition",
        verdict=cond_verdict,
        confidence=cond_conf,
        detail=f"{obs.condition.detail} (Graded {amazon_cond.value}: {cond_rule})",
        evidence=cond_evidence,
        observed_state=obs.condition.observed_state,
        amazon_condition=amazon_cond,
        model_version=vision_result.model_version,
        latency_ms=0,
    )

    # 4. Deterministic Disposition Engine
    if not vision_result.success:
        disposition = Disposition.PENDING_REVIEW
        rule_trace = f"pipeline_failure: {vision_result.error_message} → pending_review"
        record_status = RecordStatus.PENDING
        outcome_conf = 0.0
    elif obs.identity.verdict != Verdict.PASS:
        disposition = Disposition.PENDING_REVIEW
        rule_trace = f"identity={obs.identity.verdict.value} → pending_review (Rule R01/R02)"
        record_status = RecordStatus.REVIEW
        outcome_conf = obs.identity.confidence
    elif obs.completeness.verdict == Verdict.UNCERTAIN or cond_verdict == Verdict.UNCERTAIN:
        disposition = Disposition.PENDING_REVIEW
        rule_trace = f"completeness={obs.completeness.verdict.value}, condition={cond_verdict.value} → pending_review (Rule R03/R10)"
        record_status = RecordStatus.REVIEW
        outcome_conf = min(obs.completeness.confidence, cond_conf)
    elif obs.completeness.verdict == Verdict.PASS:
        if amazon_cond in (AmazonCondition.NEW, AmazonCondition.LIKE_NEW):
            disposition = Disposition.RESTOCK
            rule_trace = f"identity=PASS ∧ completeness=PASS ∧ condition={amazon_cond.value} → restock (Rule R04/R05)"
        elif amazon_cond in (AmazonCondition.VERY_GOOD, AmazonCondition.GOOD):
            disposition = Disposition.REFURBISH
            rule_trace = f"identity=PASS ∧ completeness=PASS ∧ condition={amazon_cond.value} → refurbish (Rule R06/R07)"
        elif amazon_cond == AmazonCondition.ACCEPTABLE:
            disposition = Disposition.LIQUIDATE
            rule_trace = f"identity=PASS ∧ completeness=PASS ∧ condition={amazon_cond.value} → liquidate (Rule R08)"
        elif amazon_cond == AmazonCondition.UNACCEPTABLE:
            disposition = Disposition.DISPOSE
            rule_trace = f"identity=PASS ∧ completeness=PASS ∧ condition={amazon_cond.value} → dispose (Rule R09)"
        else:
            disposition = Disposition.PENDING_REVIEW
            rule_trace = "condition=UNCERTAIN → pending_review"
        record_status = RecordStatus.COMPLETED
        outcome_conf = round((obs.identity.confidence + obs.completeness.confidence + cond_conf) / 3.0, 2)
    else:  # completeness == Verdict.FAIL
        if amazon_cond in (AmazonCondition.NEW, AmazonCondition.LIKE_NEW, AmazonCondition.VERY_GOOD):
            disposition = Disposition.REFURBISH
            rule_trace = f"completeness=FAIL ∧ condition={amazon_cond.value} → refurbish (Rule R11)"
        elif amazon_cond in (AmazonCondition.GOOD, AmazonCondition.ACCEPTABLE):
            disposition = Disposition.LIQUIDATE
            rule_trace = f"completeness=FAIL ∧ condition={amazon_cond.value} → liquidate (Rule R12)"
        else:
            disposition = Disposition.DISPOSE
            rule_trace = f"completeness=FAIL ∧ condition={amazon_cond.value} → dispose (Rule R13)"
        record_status = RecordStatus.COMPLETED
        outcome_conf = round((obs.identity.confidence + obs.completeness.confidence + cond_conf) / 3.0, 2)

    outcome = OutcomeResult(
        disposition=disposition,
        amazon_condition=amazon_cond,
        rule_trace=rule_trace,
        confidence=outcome_conf,
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
        status=record_status,
        content_hash=None,
    )

    # 5. Content Hash and Storage
    record_dict = evidence_record.model_dump(mode="json", exclude={"content_hash"})
    evidence_record.content_hash = _compute_content_hash(record_dict)

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
