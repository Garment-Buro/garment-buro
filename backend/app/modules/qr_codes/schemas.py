from __future__ import annotations

from enum import Enum

MAX_QR_PATH_BYTES = 1_024
MAX_QR_SIZE = 1_024


class QrCodeSurface(str, Enum):
    SITE = "site"
    PARTNER = "partner"
    WIDGET = "widget"
