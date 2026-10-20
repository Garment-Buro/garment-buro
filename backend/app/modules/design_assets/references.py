import posixpath
from collections.abc import Iterable
from typing import Protocol
from urllib.parse import unquote, urlsplit

from app.modules.design_assets.security import (
    DesignAssetUnavailableError,
    token_from_design_asset_path,
)


class ImageSnapshot(Protocol):
    @property
    def image(self) -> str: ...

    @property
    def customization(self) -> dict[str, object] | None: ...


def design_image_tokens(items: Iterable[ImageSnapshot]) -> list[str]:
    """Only actual image slots retain files; comments and arbitrary JSON do not."""
    tokens: set[str] = set()

    def collect(value: object) -> None:
        if not isinstance(value, str) or not value:
            return
        token = token_from_design_asset_path(value)
        if token is not None:
            tokens.add(token)
            return
        try:
            path = posixpath.normpath(unquote(urlsplit(value.replace("\\", "/")).path))
        except ValueError:
            path = value
        # Reject aliases which a browser/proxy could serve without a retained FK.
        if path == "/api/design-media" or path.startswith("/api/design-media/"):
            raise DesignAssetUnavailableError("Design image is unavailable")

    for item in items:
        collect(item.image)
        customization = item.customization or {}
        images = customization.get("modelImages")
        if isinstance(images, dict):
            for view in ("front", "back"):
                collect(images.get(view))
        decorations = customization.get("decorations")
        if isinstance(decorations, list):
            for decoration in decorations:
                if isinstance(decoration, dict):
                    collect(decoration.get("image"))
    return sorted(tokens)
