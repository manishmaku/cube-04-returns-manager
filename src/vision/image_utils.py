"""Image input validation and decoding utilities."""

import base64
import io
from pathlib import Path
from typing import Optional
from PIL import Image

from src.models.request import ImageInputItem

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_COUNT = 10
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per image


class ValidatedImage:
    """Decoded and verified image container."""
    def __init__(self, filename: str, mime_type: str, data: bytes):
        self.filename = filename
        self.mime_type = mime_type
        self.data = data
        self.size_bytes = len(data)


def validate_and_decode_image(item: ImageInputItem) -> tuple[Optional[ValidatedImage], Optional[str]]:
    """Validate and decode a single ImageInputItem.

    Returns:
        (ValidatedImage, None) on success, or (None, error_message) on failure.
    """
    if not item.filename or not item.filename.strip():
        return None, "Image filename is missing or empty."

    filename = item.filename.strip()
    mime = (item.content_type or "image/jpeg").lower().strip()
    if mime not in ALLOWED_MIME_TYPES:
        return None, f"Unsupported MIME type '{mime}' for image '{filename}'. Allowed: {sorted(ALLOWED_MIME_TYPES)}"

    raw_bytes: Optional[bytes] = None

    # Case 1: Base64 data provided
    if item.data and item.data.strip():
        data_str = item.data.strip()
        # Strip data URL prefix if present (e.g. data:image/jpeg;base64,...)
        if "," in data_str and "base64" in data_str:
            data_str = data_str.split(",", 1)[1].strip()

        try:
            raw_bytes = base64.b64decode(data_str, validate=True)
        except Exception as e:
            return None, f"Malformed base64 data for image '{filename}': {e}"

    # Case 2: Local file fallback if data is absent
    if not raw_bytes:
        # Check if file exists locally (e.g. in fixtures or data)
        local_candidates = [
            Path(filename),
            Path("data") / filename,
            Path("fixtures") / filename,
            Path("fixtures") / "returns" / filename,
        ]
        for candidate in local_candidates:
            if candidate.is_file():
                try:
                    raw_bytes = candidate.read_bytes()
                    break
                except OSError:
                    pass

    if not raw_bytes or len(raw_bytes) == 0:
        return None, f"Image '{filename}' contains empty or unresolvable data."

    if len(raw_bytes) > MAX_IMAGE_SIZE_BYTES:
        return None, f"Image '{filename}' exceeds maximum allowed size of 10 MB."

    # Verify bytes represent a valid readable image via Pillow
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()
    except Exception as e:
        return None, f"Image '{filename}' could not be decoded as a valid image: {e}"

    return ValidatedImage(filename=filename, mime_type=mime, data=raw_bytes), None


def validate_images(items: list[ImageInputItem]) -> tuple[list[ValidatedImage], list[str]]:
    """Validate a batch of image items.

    Returns:
        (valid_images, error_messages)
    """
    if len(items) > MAX_IMAGE_COUNT:
        return [], [f"Image count ({len(items)}) exceeds maximum limit of {MAX_IMAGE_COUNT} images."]

    valid_images: list[ValidatedImage] = []
    errors: list[str] = []

    for item in items:
        valid_img, err = validate_and_decode_image(item)
        if valid_img:
            valid_images.append(valid_img)
        else:
            errors.append(err or "Unknown image validation error.")

    return valid_images, errors
