"""Request building, response reading and retry timing shared by Looot and AsyncLooot.

Nothing in this module does I/O, so the sync and async clients behave the same way.
"""

from __future__ import annotations

import json
import os
import platform
import random
import uuid
from typing import Any, Dict, Mapping, Optional
from urllib.parse import quote

import httpx

from ._errors import LoootError, TopUp
from ._version import __version__

DEFAULT_BASE_URL = "https://api.looot.ai"
DEFAULT_TIMEOUT = 75.0
DEFAULT_MAX_RETRIES = 2
MAX_RETRY_WAIT_SECONDS = 30.0
MAX_AGENT_LENGTH = 64

USER_AGENT = f"looot-python/{__version__} python/{platform.python_version()}"


class Call:
    """One HTTP request, ready to send: method, path, query, encoded body and headers."""

    __slots__ = ("method", "path", "params", "content", "headers", "raw")

    def __init__(
        self,
        method: str,
        path: str,
        params: Dict[str, Any],
        content: Optional[bytes],
        headers: Dict[str, str],
        raw: bool,
    ) -> None:
        self.method = method
        self.path = path
        self.params = params
        self.content = content
        self.headers = headers
        self.raw = raw


def resolve_token(token: Optional[str]) -> Optional[str]:
    """The constructor value, else ``LOOOT_TOKEN``, else ``LOOOT_API_KEY``. Empty means none.

    An explicit ``token=""`` means "no token" and does not fall back to the environment.
    """
    if token is not None:
        return token.strip() or None
    for name in ("LOOOT_TOKEN", "LOOOT_API_KEY"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


def check_agent(agent: Optional[str]) -> Optional[str]:
    """Validates the ``X-Looot-Agent`` value: at most 64 characters."""
    if agent is None:
        return None
    agent = agent.strip()
    if len(agent) > MAX_AGENT_LENGTH:
        raise ValueError(f"agent must be at most {MAX_AGENT_LENGTH} characters, got {len(agent)}")
    return agent or None


def default_headers(agent: Optional[str]) -> Dict[str, str]:
    """Headers sent on every request."""
    headers = {"accept": "application/json", "user-agent": USER_AGENT}
    if agent:
        headers["x-looot-agent"] = agent
    return headers


def segment(value: str) -> str:
    """Percent-encodes one path segment, so ``a/b`` cannot change the path."""
    return quote(str(value), safe="")


def new_idempotency_key() -> str:
    """``sdk-`` followed by a UUID v4."""
    return f"sdk-{uuid.uuid4()}"


def clean_params(params: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Drops None values and writes booleans as lowercase ``true`` / ``false``."""
    out: Dict[str, Any] = {}
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            out[key] = [("true" if v else "false") if isinstance(v, bool) else v for v in value]
        else:
            out[key] = value
    return out


def build_call(
    method: str,
    path: str,
    *,
    token: Optional[str],
    params: Optional[Mapping[str, Any]] = None,
    body: Optional[Mapping[str, Any]] = None,
    auth: bool = True,
    raw: bool = False,
) -> Call:
    """Builds one request. Raises ``missing_token`` before anything is sent."""
    headers: Dict[str, str] = {}
    if auth:
        if not token:
            raise LoootError(
                401, "missing_token", f"{method} {path} needs a token: set LOOOT_TOKEN or pass token"
            )
        headers["authorization"] = f"Bearer {token}"
    content: Optional[bytes] = None
    if body is not None:
        content = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["content-type"] = "application/json"
    return Call(method, path, clean_params(params), content, headers, raw)


def _retry_after(response: httpx.Response, body: Any) -> Optional[float]:
    if isinstance(body, dict) and isinstance(body.get("retryAfterSeconds"), (int, float)):
        return float(body["retryAfterSeconds"])
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            return None
    return None


def read_response(call: Call, response: httpx.Response) -> Any:
    """Returns the decoded body of a 2xx answer, or raises ``LoootError``."""
    if call.raw and not response.is_error:
        return response
    data: Any
    if not response.content:
        data = None
    else:
        try:
            data = response.json()
        except ValueError:
            data = response.text
    if not response.is_error:
        return data

    status = response.status_code
    err = data.get("error") if isinstance(data, dict) else None
    err = err if isinstance(err, dict) else {}
    top_up = data.get("topUp") if isinstance(data, dict) else None
    retryable = err.get("retryable")
    hint = err.get("retryHint")
    raise LoootError(
        status,
        err.get("code") or f"http_{status}",
        err.get("message") or f"{call.method} {call.path} failed with HTTP {status}",
        err.get("requestId") or response.headers.get("x-request-id"),
        data,
        retryable=retryable if isinstance(retryable, bool) else None,
        retry_hint=hint if isinstance(hint, str) else None,
        retry_after_seconds=_retry_after(response, data),
        top_up=TopUp(top_up) if isinstance(top_up, dict) else None,
    )


def transport_error(call: Call, exc: Exception) -> LoootError:
    """Turns an httpx transport failure into ``LoootError`` with status 0."""
    code = "timeout" if isinstance(exc, httpx.TimeoutException) else "network_error"
    return LoootError(0, code, f"{call.method} {call.path} failed before an answer: {type(exc).__name__}")


def retry_delay(error: LoootError, attempt: int, max_retries: int) -> Optional[float]:
    """Seconds to wait before retry number ``attempt + 1``, or None to stop.

    Retries only retryable errors: 429, the retryable 503 codes, one 500, network failures and
    timeouts. Never a 4xx other than 429. Waits ``retry_after_seconds`` (at most 30 s) when the
    gateway gave it, else 0.5 s, 1 s, 2 s ... with a little jitter.
    """
    if attempt >= max_retries or not error.retryable:
        return None
    if 400 <= error.status < 500 and error.status != 429:
        return None
    if error.status == 500 and attempt >= 1:
        return None
    if error.retry_after_seconds is not None:
        return max(0.0, min(error.retry_after_seconds, MAX_RETRY_WAIT_SECONDS))
    return min(0.5 * (2**attempt), 8.0) + random.uniform(0, 0.1)
