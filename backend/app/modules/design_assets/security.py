import hashlib
import re
import secrets

TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
ASSET_PATH = re.compile(r"^/api/design-media/([A-Za-z0-9_-]{43})/content$")


class DesignAssetUnavailableError(ValueError):
    pass


def create_design_asset_token() -> str:
    return secrets.token_urlsafe(32)


def digest_design_asset_token(token: str) -> str:
    if not TOKEN.fullmatch(token):
        raise DesignAssetUnavailableError("Design image is unavailable")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def design_asset_path(token: str) -> str:
    digest_design_asset_token(token)
    return f"/api/design-media/{token}/content"


def token_from_design_asset_path(path: str) -> str | None:
    match = ASSET_PATH.fullmatch(path)
    return match[1] if match else None
