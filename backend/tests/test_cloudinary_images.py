from io import BytesIO

import pytest
from PIL import Image

from app.services.cloudinary_images import InvalidProfileImage, validate_image_bytes


def png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (24, 24), (80, 140, 160)).save(stream, format="PNG")
    return stream.getvalue()


def test_valid_png_is_accepted():
    data = png_bytes()
    assert validate_image_bytes(data, "image/png") == data


def test_image_larger_than_300_kib_is_rejected():
    with pytest.raises(InvalidProfileImage, match="300 KB"):
        validate_image_bytes(b"x" * (300 * 1024 + 1), "image/png")


def test_mime_type_must_match_actual_image():
    with pytest.raises(InvalidProfileImage, match="does not match"):
        validate_image_bytes(png_bytes(), "image/jpeg")


def test_svg_is_not_accepted():
    with pytest.raises(InvalidProfileImage, match="Only JPG"):
        validate_image_bytes(b"<svg></svg>", "image/svg+xml")
