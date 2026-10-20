"""A fixed card rendition of the already validated private avatar source."""

import warnings
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.modules.media.errors import PrivateStorageUnavailableError

AVATAR_CARD_SIDE = 320
AVATAR_SOURCE_SIDE = 512


def render_avatar_card(data: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if (
                    source.format != "WEBP"
                    or getattr(source, "n_frames", 1) != 1
                    or max(source.size) > AVATAR_SOURCE_SIDE
                ):
                    raise PrivateStorageUnavailableError("Avatar source is unavailable")
                source.load()
                image = source.convert("RGBA" if "A" in source.getbands() else "RGB")
                image.info.clear()
                image.thumbnail((AVATAR_CARD_SIDE, AVATAR_CARD_SIDE), Image.Resampling.LANCZOS)
                output = BytesIO()
                image.save(output, format="WEBP", quality=85, method=4)
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise PrivateStorageUnavailableError("Avatar source is unavailable") from error
