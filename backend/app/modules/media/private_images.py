import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.media.errors import UnsupportedMediaError

PRIVATE_IMAGE_MAX_BYTES = 8 * 1024 * 1024
PRIVATE_IMAGE_MAX_PIXELS = 16_777_216
PRIVATE_IMAGE_MAX_SIDE = 8192


def prepare_private_image(data: bytes, *, max_output_side: int | None = None) -> bytes:
    """Normalize a bounded single raster, preserving alpha and removing metadata."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if (
                    image.format not in {"PNG", "JPEG", "WEBP"}
                    or getattr(image, "n_frames", 1) != 1
                    or max(image.size) > PRIVATE_IMAGE_MAX_SIDE
                    or image.width * image.height > PRIVATE_IMAGE_MAX_PIXELS
                ):
                    raise UnsupportedMediaError(
                        "Only bounded single-frame JPEG, PNG or WebP images are supported"
                    )
                image.load()
                oriented = ImageOps.exif_transpose(image)
                clean = oriented.convert(
                    "RGBA"
                    if "A" in oriented.getbands() or "transparency" in oriented.info
                    else "RGB"
                )
                clean.info.clear()
                if max_output_side is not None:
                    clean.thumbnail((max_output_side, max_output_side), Image.Resampling.LANCZOS)
                output = BytesIO()
                clean.save(output, format="WEBP", lossless=True, method=4)
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise UnsupportedMediaError(
            "Only valid bounded JPEG, PNG or WebP images are supported"
        ) from error
