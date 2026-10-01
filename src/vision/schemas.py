"""Pydantic schemas for raw visual observations from Gemini multimodal analysis."""

from pydantic import BaseModel, Field
from src.models.domain import Verdict, PartStatus, ObservedState


class IdentityObservation(BaseModel):
    """Raw visual observations for product identity matching."""
    verdict: Verdict = Field(..., description="PASS if clear visual match, FAIL if wrong item, UNCERTAIN if evidence insufficient")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in identity judgment")
    claim: str = Field(..., description="Factual claim regarding item identity")
    detail: str = Field(..., description="Observations of visible model, brand, SKU markings, physical design")
    source_image: str = Field("primary_image", description="Filename of the image providing primary evidence")


class PartStatusObservation(BaseModel):
    """Presence assessment of a single required component or accessory."""
    part_name: str = Field(..., description="Name of the component from the expected parts list")
    status: PartStatus = Field(..., description="PRESENT if seen, MISSING if expected location shown empty, NOT_OBSERVED if unestablished")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this component's status")
    observation: str = Field(..., description="Visible evidence for this component")
    source_image: str = Field("primary_image", description="Filename where this observation was made")


class CompletenessObservation(BaseModel):
    """Aggregated completeness evaluation across all expected parts."""
    verdict: Verdict = Field(..., description="PASS if all parts present, FAIL if any missing, UNCERTAIN if some not observed")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall completeness confidence")
    claim: str = Field(..., description="Summary claim regarding package completeness")
    detail: str = Field(..., description="Explanation of components verified or missing")
    parts: list[PartStatusObservation] = Field(default_factory=list, description="Per-component status breakdown")
    source_image: str = Field("primary_image", description="Primary image filename for completeness assessment")


class ConditionObservation(BaseModel):
    """Raw physical condition observation (separated from condition grading)."""
    observed_state: ObservedState = Field(
        ...,
        description="factory_sealed, opened_unused, signs_of_use, damaged, empty_box, uncertain"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in physical observation")
    claim: str = Field(..., description="Physical condition claim supported by visual evidence")
    detail: str = Field(..., description="Concrete visual observations: seals, wear, scratches, packaging integrity")
    source_image: str = Field("primary_image", description="Primary image filename for condition assessment")


class VisionObservations(BaseModel):
    """Consolidated structured response from a single batched multimodal Gemini inspection."""
    identity: IdentityObservation
    completeness: CompletenessObservation
    condition: ConditionObservation
