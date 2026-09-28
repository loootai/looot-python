"""Errors raised by the looot client."""

from __future__ import annotations

from typing import Any, Optional


class LoootError(Exception):
    """Any non-2xx answer. ``code`` is the gateway error code, e.g. ``insufficient_balance``."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        request_id: Optional[str] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id
        self.body = body

    def __repr__(self) -> str:
        return f"LoootError(status={self.status}, code={self.code!r}, message={self.message!r})"
