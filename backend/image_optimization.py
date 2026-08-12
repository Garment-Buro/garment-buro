from __future__ import annotations

from io import BytesIO
from typing import Optional

from PIL import Image, ImageOps, UnidentifiedImageError


DEFAULT_WEBP_QUALITY = 88
DEFAULT_MAX_DIMENSION = 2400


def optimize_image_bytes(
    data: bytes,
    *,
    quality: int = DEFAULT_WEBP_QUALITY,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
) -> Optional[bytes]:
    """Return a smaller WebP version, or None when conversion is not useful."""
    if not data:
        return None

    try:
        with Image.open(BytesIO(data)) as source:
            if getattr(source, "n_frames", 1) > 1:
                return None

            icc_profile = source.info.get("icc_profile")
            source.load()
            image = ImageOps.exif_transpose(source)

            if max(image.size) > max_dimension:
                image.thumbnail(
                    (max_dimension, max_dimension),
                    Image.Resampling.LANCZOS,
                )

            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            image = image.convert("RGBA" if has_alpha else "RGB")

            output = BytesIO()
            save_options = {
                "format": "WEBP",
                "quality": quality,
                "method": 6,
            }
            if has_alpha:
                save_options.update({"alpha_quality": 100, "exact": True})
            if icc_profile:
                save_options["icc_profile"] = icc_profile

            image.save(output, **save_options)
            optimized = output.getvalue()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        return None

    return optimized if len(optimized) < len(data) else None
