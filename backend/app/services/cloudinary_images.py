from __future__ import annotations

from io import BytesIO
from typing import Any
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

PROFILE_IMAGE_MAX_BYTES = 300 * 1024
MIME_TO_FORMAT = {
    "image/jpeg": {"JPEG"},
    "image/jpg": {"JPEG"},
    "image/png": {"PNG"},
    "image/webp": {"WEBP"},
}


class InvalidProfileImage(ValueError):
    pass


def validate_image_bytes(data: bytes, content_type: str | None) -> bytes:
    """Validate actual image content, not only the browser-provided MIME type."""
    if not data:
        raise InvalidProfileImage("Choose an image before uploading.")
    if len(data) > min(settings.max_upload_bytes, PROFILE_IMAGE_MAX_BYTES):
        raise InvalidProfileImage("Profile photos must be 300 KB or smaller.")
    mime = (content_type or "").lower().strip()
    if mime not in settings.image_mime_types or mime not in MIME_TO_FORMAT:
        raise InvalidProfileImage("Only JPG, PNG and WebP images are supported.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            image_format = (image.format or "").upper()
            if image.width < 1 or image.height < 1 or image.width * image.height > 20_000_000:
                raise InvalidProfileImage("Image dimensions are too large.")
            if image_format not in MIME_TO_FORMAT[mime]:
                raise InvalidProfileImage("The file content does not match its image type.")
            image.verify()
            # Re-open and decode every pixel so malformed/truncated images are rejected.
            image = Image.open(BytesIO(data))
            image.load()
    except InvalidProfileImage:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidProfileImage("The uploaded file is not a valid image.") from exc
    return data


def _cloudinary_modules():
    if not all((settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret)):
        raise RuntimeError("Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET.")
    import cloudinary
    from cloudinary import uploader, utils

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    return uploader, utils


def upload_image(data: bytes, *, folder: str, public_id: str) -> tuple[str, str]:
    """Upload a validated image and return a compact, transformed HTTPS delivery URL."""
    uploader, utils = _cloudinary_modules()
    result: dict[str, Any] = uploader.upload(
        data,
        folder=folder.strip("/"),
        public_id=public_id,
        overwrite=True,
        unique_filename=False,
        use_filename=False,
        resource_type="image",
        invalidate=True,
    )
    asset_public_id = str(result["public_id"])
    url, _options = utils.cloudinary_url(
        asset_public_id,
        secure=True,
        version=result.get("version"),
        transformation=[
            {
                "width": 512,
                "height": 512,
                "crop": "fill",
                "gravity": "auto",
                "quality": "auto:eco",
                "fetch_format": "auto",
            }
        ],
    )
    return url, asset_public_id


def delete_image(public_id: str | None) -> None:
    if not public_id:
        return
    uploader, _utils = _cloudinary_modules()
    uploader.destroy(public_id, resource_type="image", invalidate=True)
