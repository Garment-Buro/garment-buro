from io import BytesIO

import pytest
from PIL import Image

from app.modules.media.private_images import prepare_private_image
from app.modules.media.service import UnsupportedMediaError


def test_orientation_is_applied_and_private_exif_is_removed():
    image = Image.new("RGB", (12, 8), (30, 60, 90))
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise.
    exif[315] = "private author"
    source = BytesIO()
    image.save(source, format="JPEG", exif=exif)
    result = prepare_private_image(source.getvalue())
    with Image.open(BytesIO(result)) as decoded:
        assert decoded.size == (8, 12)
        assert decoded.format == "WEBP"
        assert "exif" not in decoded.info
    assert b"private author" not in result


def test_animated_image_and_excessive_pixel_count_are_rejected():
    output = BytesIO()
    Image.new("RGBA", (8, 8), "red").save(
        output,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGBA", (8, 8), "blue")],
        duration=100,
    )
    with pytest.raises(UnsupportedMediaError):
        prepare_private_image(output.getvalue())
    output = BytesIO()
    Image.new("RGB", (4097, 4096), "red").save(output, format="PNG")
    with pytest.raises(UnsupportedMediaError):
        prepare_private_image(output.getvalue())
