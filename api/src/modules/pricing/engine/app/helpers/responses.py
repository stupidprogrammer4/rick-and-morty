from typing import Any

import httpx

from src.modules.pricing.engine.domain.quotes import (
    ErrorQuote,
    HTTPErrorQuote,
)
from src.modules.pricing.sources.domain.enums import ErrorType


def _body(resp: httpx.Response | None) -> HTTPErrorQuote | None:
    detail = None
    if resp is not None:
        detail = HTTPErrorQuote(
            raw_content="", status_code=str(resp.status_code), json=None
        )
    return detail


def http_error(exc: httpx.HTTPError) -> ErrorQuote:
    """
    Desc: Map an HTTP exception into the source error shape.
    Args:
        exc (httpx.HTTPError): Transport exception.
    Returns:
        return (ErrorQuote): Source error details.
    """
    resp = exc.response if isinstance(exc, httpx.HTTPStatusError) else None
    error = ErrorQuote(
        error_type=ErrorType.HTTP_ERROR,
        message=type(exc).__name__,
        http_error=_body(resp),
    )
    return error


def logical_error(exc: Exception) -> ErrorQuote:
    """
    Desc: Map a parsing failure into the source error shape.
    Args:
        exc (Exception): Parsing failure.
    Returns:
        return (ErrorQuote): Source error details.
    """
    error = ErrorQuote(
        error_type=ErrorType.LOGICAL_ERROR,
        message=type(exc).__name__,
        http_error=None,
    )
    return error


def json_path(payload: Any, *keys: str | int) -> Any:
    """
    Desc: Read a nested path from an already decoded response.
    Args:
        payload (Any): Decoded response.
        keys (str | int): Path components.
    Returns:
        return (Any): Value at the requested path.
    """
    node = payload
    for key in keys:
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            raise ValueError(f"missing field {key!r} in response") from None
    return node
