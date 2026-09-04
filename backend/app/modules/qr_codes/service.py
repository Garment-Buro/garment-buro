from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

import qrcode
from PIL import Image
from qrcode.exceptions import DataOverflowError

from app.core.config import Settings
from app.modules.qr_codes.schemas import MAX_QR_PATH_BYTES, QrCodeSurface


class QrCodeValidationError(ValueError):
    """Raised when a QR target is outside an approved web surface."""


@dataclass(frozen=True, slots=True)
class QrCodeArtifact:
    content: bytes
    target_url: str
    etag: str


class QrCodeService:
    def __init__(self, settings: Settings) -> None:
        self._origins = {
            QrCodeSurface.SITE: self._validate_origin(settings.public_base_url),
            QrCodeSurface.PARTNER: self._validate_origin(settings.partner_public_base_url),
            QrCodeSurface.WIDGET: self._validate_origin(settings.widget_public_base_url),
        }

    def build_target(self, path: str, surface: QrCodeSurface) -> str:
        safe_path = self._validate_path(path)
        return f"{self._origins[surface]}{safe_path}"

    def generate_png(self, path: str, surface: QrCodeSurface, size: int) -> QrCodeArtifact:
        target_url = self.build_target(path, surface)
        code = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        code.add_data(target_url)
        try:
            code.make(fit=True)
        except DataOverflowError as error:
            raise QrCodeValidationError("path is too large for a QR code") from error

        image = code.make_image(fill_color="black", back_color="white").convert("RGB")
        if image.size != (size, size):
            image = image.resize((size, size), Image.Resampling.NEAREST)

        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        content = output.getvalue()
        etag = hashlib.sha256(content).hexdigest()
        return QrCodeArtifact(content=content, target_url=target_url, etag=etag)

    @staticmethod
    def header_safe_target(target_url: str) -> str:
        return quote(target_url, safe=":/?#[]@!$&'()*+,;=%")

    @staticmethod
    def _validate_origin(value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise RuntimeError("QR code surface URLs must be absolute HTTP(S) origins")
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _validate_path(value: str) -> str:
        if not value or len(value.encode("utf-8")) > MAX_QR_PATH_BYTES or not value.startswith("/"):
            raise QrCodeValidationError("path must be a root-relative site path")
        if value.startswith("//") or "\\" in value or any(ord(char) < 32 for char in value):
            raise QrCodeValidationError("path must be a safe root-relative site path")

        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            raise QrCodeValidationError("absolute and protocol-relative URLs are not allowed")

        decoded_path = parsed.path
        for _ in range(3):
            next_value = unquote(decoded_path)
            if next_value == decoded_path:
                break
            decoded_path = next_value
        if (
            decoded_path.startswith("//")
            or "\\" in decoded_path
            or any(segment in {".", ".."} for segment in decoded_path.split("/"))
            or any(ord(char) < 32 for char in decoded_path)
        ):
            raise QrCodeValidationError("path must not escape the selected site surface")

        return value
