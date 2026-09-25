"""Evidence contract response models conforming to Buildathon schema (RULES.md §3.2)."""

from typing import Optional
from pydantic import BaseModel, Field

from src.models.domain import (
    Verdict,
    PartStatus,
    ObservedState,
    AmazonCondition,
    Disposition,
    RecordStatus,
)


class EvidenceItem(BaseModel):
    """Specific observation evidence supporting a check verdict."""
    evidence_id: str = Field(..., description="Unique evidence identifier")
    claim: str = Field(..., description="Fact or assertion being established")
    evidence_type: str = Field(..., description="Type of evidence: visual_match, visual_observation, etc.")
    source: str = Field(..., description="Reference image or data source")
    observation: str = Field(..., description="Concrete visual observation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this observation")


class PartStatusItem(BaseModel):
    """Presence status of an individual expected component."""
    part: str = Field(..., description="Name of the component or accessory")
    status: PartStatus = Field(..., description="PRESENT, MISSING, or NOT_OBSERVED")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class CheckResult(BaseModel):
    """Individual assessment check (identity, completeness, condition)."""
    check_key: str = Field(..., description="Check identifier: identity, completeness, condition")
    verdict: Verdict = Field(..., description="PASS, FAIL, or UNCERTAIN")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Aggregate confidence score")
    detail: str = Field(..., description="Human-readable explanation of the judgment")
    evidence: list[EvidenceItem] = Field(default_factory=list, description="Supporting evidence items")
    parts_status: Optional[list[PartStatusItem]] = Field(None, description="Component status breakdown for completeness")
    observed_state: Optional[ObservedState] = Field(None, description="Operator/visual observed packaging state")
    amazon_condition: Optional[AmazonCondition] = Field(None, description="Classified Amazon condition grade")
    model_version: Optional[str] = Field(None, description="Model identifier used for analysis")
    latency_ms: Optional[int] = Field(None, description="Check execution latency in milliseconds")


class OutcomeResult(BaseModel):
    """Final decision outcome for the returned parcel."""
    disposition: Disposition = Field(..., description="restock, refurbish, liquidate, dispose, pending_review")
    amazon_condition: Optional[AmazonCondition] = Field(None, description="Overall Amazon condition grade")
    rule_trace: str = Field(..., description="Explicit rule path explaining the disposition choice")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall outcome confidence")


class OverrideRecord(BaseModel):
    """Audit trail for human operator overrides (RULES.md §3.3)."""
    override_id: str = Field(..., description="Unique override identifier")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of override")
    operator_id: str = Field(..., description="Operator who performed the override")
    field: str = Field(..., description="Field overridden (e.g. disposition, condition)")
    original_value: str = Field(..., description="Original agent-determined value")
    revised_value: str = Field(..., description="Operator-revised value")
    reason: str = Field(..., description="Justification for the override")
    check_key: Optional[str] = Field(None, description="Associated check key if check-level override")


class ImageRecord(BaseModel):
    """Metadata for an image evaluated during return assessment."""
    image_id: str = Field(..., description="Unique image identifier")
    filename: str = Field(..., description="Original image filename")
    storage_path: Optional[str] = Field(None, description="Tenant-isolated storage path")
    content_type: Optional[str] = Field("image/jpeg", description="MIME type")
    size_bytes: Optional[int] = Field(0, description="Image file size in bytes")
    hash_sha256: Optional[str] = Field(None, description="SHA-256 digest of image content")


class SubjectInfo(BaseModel):
    """Unit and catalogue subject information."""
    unit_id: str = Field(..., description="Cross-repo operational chain join key")
    order_id: Optional[str] = Field(None, description="Original order identifier")
    ordered_sku: Optional[str] = Field(None, description="Ordered SKU")
    ordered_asin: Optional[str] = Field(None, description="Ordered ASIN")


class EvidenceRecord(BaseModel):
    """Complete official Evidence Record conforming to Buildathon contract."""
    record_id: str = Field(..., description="Unique RTN record identifier (e.g. RTN-0003)")
    schema_version: str = Field("1.0.0", description="Evidence contract schema version")
    organization_id: str = Field(..., description="Tenant organization ID")
    client_id: Optional[str] = Field(None, description="Client ID")
    agent: str = Field("returns-manager@1.0.0", description="Agent version identifier")
    subject: SubjectInfo = Field(..., description="Subject unit being assessed")
    captured_at: str = Field(..., description="ISO 8601 UTC capture timestamp")
    operator_label: Optional[str] = Field(None, description="Handling operator ID")
    images: list[ImageRecord] = Field(default_factory=list, description="Evaluated return photographs")
    checks: list[CheckResult] = Field(default_factory=list, description="Identity, completeness, condition checks")
    outcome: OutcomeResult = Field(..., description="Final disposition outcome")
    overrides: list[OverrideRecord] = Field(default_factory=list, description="Preserved operator overrides")
    status: RecordStatus = Field(RecordStatus.COMPLETED, description="Record lifecycle status")
    content_hash: Optional[str] = Field(None, description="SHA-256 integrity hash of record contents")


class HealthResponse(BaseModel):
    """Service health response."""
    status: str = "healthy"
    service: str = "returns-manager"
    version: str = "1.0.0"
    timestamp: str
