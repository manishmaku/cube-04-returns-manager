"""API Request models for the Returns Manager."""

from typing import Optional
from pydantic import BaseModel, Field


class ImageInputItem(BaseModel):
    """Image data representation for API payloads."""
    filename: str = Field(..., description="Image filename (e.g. UNIT-0003_1.jpg)")
    data: Optional[str] = Field(None, description="Base64-encoded image string, or relative file reference")
    content_type: Optional[str] = Field("image/jpeg", description="MIME type")


class ReturnAssessmentRequest(BaseModel):
    """Input payload for POST /agent assessment."""
    organization_id: str = Field(..., description="Tenant organization ID (e.g. org_demo_alpha, org_demo_bravo)")
    client_id: Optional[str] = Field(None, description="Client account within organization")
    unit_id: str = Field(..., description="Cross-chain unit identifier (e.g. UNIT-0003)")
    order_id: str = Field(..., description="Original order reference (e.g. ORD-DUMMY-50003)")
    ordered_sku: str = Field(..., description="Ordered SKU from seller catalogue (e.g. SKU-PUZZLE-500)")
    ordered_asin: str = Field(..., description="Ordered ASIN (e.g. B0DUMMY729)")
    parts_list: list[str] = Field(default_factory=list, description="Expected components/accessories list")
    operator_id: Optional[str] = Field("op_default", description="Operator handling the physical parcel")
    images: list[ImageInputItem] = Field(default_factory=list, description="Returned parcel photographs")

    model_config = {
        "json_schema_extra": {
            "example": {
                "organization_id": "org_demo_alpha",
                "client_id": "client_001",
                "unit_id": "UNIT-0003",
                "order_id": "ORD-DUMMY-50003",
                "ordered_sku": "SKU-PUZZLE-500",
                "ordered_asin": "B0DUMMY729",
                "parts_list": ["puzzle pieces", "poster"],
                "operator_id": "op_chen",
                "images": [
                    {"filename": "UNIT-0003_1.jpg", "content_type": "image/jpeg"}
                ]
            }
        }
    }
