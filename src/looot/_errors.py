"""The one error type the client raises, and the table that says which errors are retryable."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

_WAIT_SAME_KEY = "Wait retry_after_seconds, then retry with the same idempotency key."

# code -> (retryable, what the caller does). From the SDK contract, section 6.1.
_CODES: Dict[str, Tuple[bool, str]] = {
    "validation_error": (False, "Fix the field named in the message or in error.details."),
    "runs_cursor_invalid": (False, "Page again with no cursor."),
    "unauthorized": (False, "Create a new token at looot.ai and set LOOOT_TOKEN."),
    "token_revoked": (False, "Create a new token at looot.ai and set LOOOT_TOKEN."),
    "missing_token": (False, "Set LOOOT_TOKEN or pass token= to Looot()."),
    "insufficient_balance": (False, "Top up at top_up.url, then run again with a new idempotency key."),
    "key_spend_limit_reached": (False, "Raise the token's monthly spend limit in the dashboard."),
    "forbidden": (False, "Add the missing scope to the token."),
    "platform_operator_required": (False, "This route is for looot operators only."),
    "idempotency_conflict": (False, "Use a new idempotency key for a different request."),
    "catalog_cursor_stale": (False, "Page again with no cursor."),
    "rows_mode_unsupported": (False, "Drop the rows option."),
    "too_many_inflight_runs": (True, _WAIT_SAME_KEY),
    "run_rate_limited": (True, _WAIT_SAME_KEY),
    "rate_limit_exceeded": (True, _WAIT_SAME_KEY),
    "internal_error": (True, "Retry once. If it repeats, report the request_id."),
    "catalog_loading": (True, _WAIT_SAME_KEY),
    "storage_busy": (True, _WAIT_SAME_KEY),
    "storage_uncertain": (True, _WAIT_SAME_KEY),
    "runtime_bridge_timeout": (True, _WAIT_SAME_KEY),
    "billing_unavailable": (False, "Billing is unavailable right now. Try again later."),
    "network_error": (True, "Check the network, then retry with the same idempotency key."),
    "timeout": (True, "Retry with the same idempotency key, or pass a larger timeout=."),
}


def default_retryable(status: int, code: str) -> bool:
    """Whether an error is worth retrying, from its code, else from its HTTP status."""
    if code in _CODES:
        return _CODES[code][0]
    return status in (429, 500, 502, 503, 504)


def default_retry_hint(code: str) -> Optional[str]:
    """One sentence on what to do next, for the codes the contract lists."""
    entry = _CODES.get(code)
    return entry[1] if entry else None


class TopUp:
    """Where to add credit, read from a 402 ``insufficient_balance`` body."""

    __slots__ = ("checkout_url", "dashboard_url", "minimum_usd", "raw")

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.raw = raw
        self.checkout_url: Optional[str] = raw.get("checkoutUrl")
        self.dashboard_url: Optional[str] = raw.get("dashboardUrl")
        self.minimum_usd: Optional[float] = raw.get("minimumUsd")

    @property
    def url(self) -> Optional[str]:
        """The checkout link when a payment session is open, else the dashboard top-up page."""
        return self.checkout_url or self.dashboard_url

    def __repr__(self) -> str:
        return f"TopUp(url={self.url!r})"


class LoootError(Exception):
    """Raised for every non-2xx answer, a network failure, a timeout and a missing token.

    A run that failed is not an error. It comes back as a run with ``status == "failed"``.

    Attributes:
        status: HTTP status, or 0 when no answer came back.
        code: the gateway's ``error.code`` (``insufficient_balance``), else ``http_<status>``.
        message: the gateway's message, or a sentence naming the method and path.
        request_id: ``error.requestId``, else the ``x-request-id`` header.
        body: the decoded body, or the raw text when it is not JSON.
        retryable: True when the same request may succeed later.
        retry_hint: one sentence on what to do next.
        retry_after_seconds: how long the gateway asked to wait, when it said.
        top_up: on a 402, where to add credit.
    """

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        request_id: Optional[str] = None,
        body: Any = None,
        *,
        retryable: Optional[bool] = None,
        retry_hint: Optional[str] = None,
        retry_after_seconds: Optional[float] = None,
        top_up: Optional[TopUp] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id
        self.body = body
        self.retryable = default_retryable(status, code) if retryable is None else retryable
        self.retry_hint = retry_hint or default_retry_hint(code)
        self.retry_after_seconds = retry_after_seconds
        self.top_up = top_up

    def __str__(self) -> str:
        text = f"{self.code}: {self.message}"
        return f"{text} (request {self.request_id})" if self.request_id else text

    def __repr__(self) -> str:
        return (
            f"LoootError(status={self.status}, code={self.code!r}, message={self.message!r}, "
            f"request_id={self.request_id!r}, retryable={self.retryable})"
        )
