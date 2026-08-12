from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request

from app.modules.payments.retry_router import _parse_order_id, _require_empty_body


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
            "path": "/api/orders/1/payment-attempts",
            "headers": headers,
        },
        receive,
    )


def test_payment_retry_requires_empty_actual_stream() -> None:
    request = _streaming_request([b"", b"unexpected"])

    with pytest.raises(HTTPException) as failed:
        asyncio.run(_require_empty_body(request))

    assert failed.value.status_code == 400
    assert failed.value.headers == {"Cache-Control": "no-store"}


@pytest.mark.parametrize("content_length", ["invalid", "-1", "1"])
def test_payment_retry_rejects_invalid_or_nonempty_content_length(
    content_length: str,
) -> None:
    request = _streaming_request([b""], content_length=content_length)

    with pytest.raises(HTTPException) as failed:
        asyncio.run(_require_empty_body(request))

    assert failed.value.status_code == 400
    assert failed.value.headers == {"Cache-Control": "no-store"}


@pytest.mark.parametrize("value", ["0", "-1", "01", "invalid"])
def test_payment_retry_order_id_is_canonical_positive_integer(value: str) -> None:
    with pytest.raises(HTTPException) as failed:
        _parse_order_id(value)

    assert failed.value.status_code == 404
    assert failed.value.headers == {"Cache-Control": "no-store"}
