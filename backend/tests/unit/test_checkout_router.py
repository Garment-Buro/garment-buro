from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request

from app.modules.checkout.router import _read_limited_body
from app.modules.orders.schemas import MAX_ORDER_PAYLOAD_BYTES


def _streaming_request(chunks: list[bytes], *, content_length: str | None = None) -> Request:
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ]

    async def receive() -> dict[str, object]:
        return messages.pop(0)

    headers = []
    if content_length is not None:
        headers.append((b"content-length", content_length.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/orders",
            "headers": headers,
        },
        receive,
    )


def test_checkout_stream_limit_applies_without_content_length() -> None:
    request = _streaming_request(
        [b"x" * MAX_ORDER_PAYLOAD_BYTES, b"x"],
    )

    with pytest.raises(HTTPException) as failed:
        asyncio.run(_read_limited_body(request))

    assert failed.value.status_code == 413
    assert failed.value.headers == {"Cache-Control": "no-store"}


@pytest.mark.parametrize("content_length", ["invalid", "-1"])
def test_checkout_rejects_invalid_content_length(content_length: str) -> None:
    request = _streaming_request([b"{}"], content_length=content_length)

    with pytest.raises(HTTPException) as failed:
        asyncio.run(_read_limited_body(request))

    assert failed.value.status_code == 400
    assert failed.value.headers == {"Cache-Control": "no-store"}
