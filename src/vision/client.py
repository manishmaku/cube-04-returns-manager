"""Multimodal vision client for Returns parcel analysis using Gemini 2.5 Flash."""

import time
from typing import Optional
from pydantic import BaseModel, Field

from src.config import GEMINI_API_KEY, GEMINI_MODEL
from src.models.domain import ObservedState, PartStatus, Verdict
from src.vision.image_utils import ValidatedImage
from src.vision.schemas import (
    CompletenessObservation,
    ConditionObservation,
    IdentityObservation,
    PartStatusObservation,
    VisionObservations,
)


class VisionPipelineResult(BaseModel):
    """Result returned by the vision analysis pipeline."""
    success: bool = Field(..., description="Whether model inference and validation succeeded")
    observations: Optional[VisionObservations] = Field(None, description="Validated observations if successful")
    model_version: str = Field(..., description="Model identifier used")
    latency_ms: int = Field(0, description="Inference latency in milliseconds")
    error_message: Optional[str] = Field(None, description="Error reason if success is False")


def create_fallback_observations(
    ordered_sku: str,
    ordered_asin: str,
    parts_list: list[str],
    reason: str,
    primary_image: str = "primary_image",
) -> VisionObservations:
    """Create conservative fallback observations with UNCERTAIN verdicts when vision is unavailable."""
    return VisionObservations(
        identity=IdentityObservation(
            verdict=Verdict.UNCERTAIN,
            confidence=0.0,
            claim="Product identity cannot be verified without visual inference",
            detail=f"Visual verification unavailable: {reason}",
            source_image=primary_image,
        ),
        completeness=CompletenessObservation(
            verdict=Verdict.UNCERTAIN,
            confidence=0.0,
            claim="Component completeness cannot be established without visual inference",
            detail=f"Completeness inspection unavailable: {reason}",
            parts=[
                PartStatusObservation(
                    part_name=part,
                    status=PartStatus.NOT_OBSERVED,
                    confidence=0.0,
                    observation=f"Visual verification unavailable: {reason}",
                    source_image=primary_image,
                )
                for part in parts_list
            ],
            source_image=primary_image,
        ),
        condition=ConditionObservation(
            observed_state=ObservedState.UNCERTAIN,
            confidence=0.0,
            claim="Condition unverified due to vision pipeline error",
            detail=f"Physical condition inspection unavailable: {reason}",
            source_image=primary_image,
        ),
    )


class GeminiVisionClient:
    """Production-oriented Gemini client for batched multimodal returns inspection."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model_name = model_name or GEMINI_MODEL or "gemini-2.5-flash"
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY
        self._client = None

    def _get_client(self):
        """Lazy initialization of google-genai Client."""
        if self._client is None and self.api_key:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def build_prompt(self, ordered_sku: str, ordered_asin: str, parts_list: list[str]) -> str:
        """Construct the prompt instructing Gemini on evidence-backed returns inspection."""
        parts_str = ", ".join(f"'{p}'" for p in parts_list) if parts_list else "None specified"
        return f"""You are the Returns Manager inspection agent at an e-commerce fulfillment and returns center.
Analyze the provided photographs of a customer-returned parcel.

Expected Order / Catalogue Information:
- Ordered SKU: {ordered_sku}
- Ordered ASIN: {ordered_asin}
- Expected Components/Accessories: [{parts_str}]

Perform a rigorous, evidence-backed inspection answering three questions:

1. IDENTITY VERIFICATION:
- Examine the physical product, packaging, brand name, markings, labels, and design.
- Compare them against the expected SKU ({ordered_sku}) and ASIN ({ordered_asin}).
- Set verdict to 'PASS' ONLY if the visual evidence clearly demonstrates it is the ordered product.
- Set verdict to 'FAIL' if it is visibly a different product or model.
- Set verdict to 'UNCERTAIN' if markings are obscured, blurry, or insufficient to prove identity.
- Never claim a match without visible evidence.

2. COMPLETENESS VERIFICATION:
- For each item in the expected accessories list: [{parts_str}], evaluate its presence.
- Status MUST be one of:
  * 'PRESENT': Clearly observed in at least one photograph.
  * 'MISSING': Expected location/recess is clearly visible and empty.
  * 'NOT_OBSERVED': Not visible in the photographs, but cannot definitively establish absence (e.g. sealed packaging, obscured angle).
- Set overall completeness verdict to:
  * 'PASS' if all required parts are PRESENT.
  * 'FAIL' if any part is confirmed MISSING.
  * 'UNCERTAIN' if any parts are NOT_OBSERVED and none are confirmed MISSING.

3. PHYSICAL CONDITION OBSERVATION:
- Observe the physical packaging and merchandise condition.
- observed_state MUST be exactly one of:
  * 'factory_sealed': Original manufacturer shrink-wrap / factory seal is intact and unopened.
  * 'opened_unused': Packaging was opened, but the contents appear completely pristine and unused.
  * 'signs_of_use': Shows signs of handling, wear, or cosmetic blemishes.
  * 'damaged': Shows physical, structural, or cosmetic damage (dents, cracks, tears).
  * 'empty_box': Package is empty; product is missing.
  * 'uncertain': Evidence is ambiguous or cannot establish condition.
- Provide objective, concrete observations in 'detail'. Do not classify into Amazon condition; focus solely on physical facts observed.

Cite the specific image filename where each piece of evidence was observed.
Respond strictly in valid JSON matching the requested schema.
"""

    def analyze_return(
        self,
        ordered_sku: str,
        ordered_asin: str,
        parts_list: list[str],
        images: list[ValidatedImage],
    ) -> VisionPipelineResult:
        """Execute a batched multimodal visual inspection across all provided return images.

        Fail-open guarantee: If API key is missing, network fails, or model returns invalid JSON,
        this method returns a VisionPipelineResult with success=False and fallback UNCERTAIN observations.
        """
        primary_filename = images[0].filename if images else "no_image_provided"

        # Check for missing API key
        if not self.api_key or not self.api_key.strip():
            return VisionPipelineResult(
                success=False,
                observations=create_fallback_observations(
                    ordered_sku, ordered_asin, parts_list, "GEMINI_API_KEY is not configured", primary_filename
                ),
                model_version=f"{self.model_name} (unconfigured)",
                latency_ms=0,
                error_message="GEMINI_API_KEY environment variable is not configured.",
            )

        # Check for missing images
        if not images:
            return VisionPipelineResult(
                success=False,
                observations=create_fallback_observations(
                    ordered_sku, ordered_asin, parts_list, "No valid photographic evidence provided", primary_filename
                ),
                model_version=self.model_name,
                latency_ms=0,
                error_message="No valid images were provided for visual analysis.",
            )

        prompt = self.build_prompt(ordered_sku, ordered_asin, parts_list)
        start_time = time.perf_counter()

        try:
            from google.genai import types

            client = self._get_client()
            if not client:
                raise RuntimeError("Failed to initialize Google GenAI client.")

            contents = [
                types.Part.from_bytes(data=img.data, mime_type=img.mime_type)
                for img in images
            ]
            contents.append(prompt)

            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VisionObservations,
                    temperature=0.1,
                ),
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Validate response structure with Pydantic
            if not response.text:
                raise ValueError("Gemini returned an empty text response.")

            parsed_observations = VisionObservations.model_validate_json(response.text)

            return VisionPipelineResult(
                success=True,
                observations=parsed_observations,
                model_version=self.model_name,
                latency_ms=latency_ms,
                error_message=None,
            )

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            err_msg = f"Gemini vision inference failed: {type(e).__name__} - {e}"
            return VisionPipelineResult(
                success=False,
                observations=create_fallback_observations(
                    ordered_sku, ordered_asin, parts_list, err_msg, primary_filename
                ),
                model_version=self.model_name,
                latency_ms=latency_ms,
                error_message=err_msg,
            )
