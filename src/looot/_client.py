"""A small client for the looot REST API over httpx.

Written from the public OpenAPI (https://api.looot.ai/openapi.json) and the agent guide
(https://api.looot.ai/llms-full.txt). Methods return the decoded JSON as plain dicts.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Literal, Mapping, Optional, Union

import httpx

from ._errors import LoootError

DEFAULT_BASE_URL = "https://api.looot.ai"

Prefer = Literal["balanced", "cheapest", "reliable", "fastest"]
Fallback = Union[bool, Dict[str, Any]]
JSON = Dict[str, Any]


def _clean(params: Mapping[str, Any]) -> Dict[str, Any]:
    """Drops None values and turns booleans into the lowercase strings the API expects."""
    out: Dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        out[key] = ("true" if value else "false") if isinstance(value, bool) else value
    return out


class Looot:
    """Client for the looot REST API.

    ``token`` defaults to the ``LOOOT_TOKEN`` environment variable. Browsing the catalog
    overview and the public catalog needs no token.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 75.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        env_token = (os.environ.get("LOOOT_TOKEN") or "").strip() or None
        self._token = token if token is not None else env_token
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"accept": "application/json"},
        )

    # ---- lifecycle ----

    def close(self) -> None:
        """Closes the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "Looot":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- free, no token ----

    def catalog_overview(
        self,
        *,
        depth: Optional[Literal["summary", "platforms", "jobs", "full"]] = None,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> JSON:
        """Free, no token. Categories, platforms and jobs with counts and cheapest prices."""
        return self._request(
            "GET",
            "/v1/catalog/overview",
            params={"depth": depth, "category": category, "platform": platform, "topic": topic},
            auth=False,
        )

    def public_catalog(
        self,
        *,
        q: Optional[str] = None,
        capability: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> JSON:
        """Free, no token. Published items with parameters and price.

        ``capability`` is the job id with dots turned into underscores (people_email_verify).
        """
        return self._request(
            "GET",
            "/v1/public-catalog",
            params={
                "q": q,
                "capability": capability,
                "category": category,
                "provider": provider,
                "limit": limit,
                "cursor": cursor,
            },
            auth=False,
        )

    def public_catalog_item(self, catalog_item_id: str) -> JSON:
        """Free, no token. One published catalog item."""
        return self._request("GET", f"/v1/public-catalog/{_path(catalog_item_id)}", auth=False)

    # ---- free, token ----

    def search(
        self,
        q: Optional[str] = None,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        provider: Optional[str] = None,
        capability: Optional[str] = None,
        keyless: Optional[bool] = None,
        verified: Optional[bool] = None,
        mock: Optional[bool] = None,
        max_price_micros: Optional[int] = None,
        prefer: Optional[Prefer] = None,
    ) -> JSON:
        """Free, needs catalog.read. Ranked search across every provider."""
        return self._request(
            "GET",
            "/v1/catalog/search",
            params={
                "q": q,
                "limit": limit,
                "offset": offset,
                "category": category,
                "platform": platform,
                "provider": provider,
                "capability": capability,
                "keyless": keyless,
                "verified": verified,
                "mock": mock,
                "maxPriceMicros": max_price_micros,
                "prefer": prefer,
            },
        )

    def inspect(self, endpoint_id: str) -> JSON:
        """Free, needs a token. Input and output schema, price formula, estimated max cost."""
        return self._request("GET", f"/v1/operations/{_path(endpoint_id)}")

    # ---- paid ----

    def run(
        self,
        endpoint_id: str,
        input: Mapping[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        wait: Union[int, float, bool, None] = None,
        fallback: Optional[Fallback] = None,
        output: Optional[Mapping[str, Any]] = None,
    ) -> JSON:
        """Paid. Holds the estimated cost, runs, settles.

        A returned run is not success: check ``run["status"]`` and ``run["error"]``.
        ``idempotency_key`` is generated when omitted; pass your own to retry safely.
        ``wait`` is seconds (0 to 60); without it the run comes back queued.
        """
        body: Dict[str, Any] = {
            "endpointId": endpoint_id,
            "input": dict(input),
            "idempotencyKey": idempotency_key or f"sdk-{uuid.uuid4()}",
        }
        if fallback is not None:
            body["fallback"] = fallback
        if output is not None:
            body["output"] = dict(output)
        params = {} if wait is None else {"wait": wait}
        return self._request("POST", "/v1/runs", params=params, json=body)

    def run_job(
        self,
        job: str,
        input: Mapping[str, Any],
        *,
        prefer: Optional[Prefer] = None,
        fallback: Optional[Fallback] = None,
        wait: Union[int, float, bool, None] = None,
        idempotency_key: Optional[str] = None,
    ) -> JSON:
        """Paid. Runs a job (endpointId ``job:<id>``); looot picks the provider.

        ``prefer`` is sent as ``fallback.prefer``, which turns fallback on.
        """
        fb: Optional[Fallback] = fallback
        if prefer is not None:
            fb = {**fallback, "prefer": prefer} if isinstance(fallback, dict) else {"prefer": prefer}
        return self.run(f"job:{job}", input, idempotency_key=idempotency_key, wait=wait, fallback=fb)

    # ---- runs and balance ----

    def get_run(self, run_id: str) -> JSON:
        """One run: status, result, cost and error."""
        return self._request("GET", f"/v1/runs/{_path(run_id)}")

    def list_runs(
        self,
        *,
        status: Optional[str] = None,
        capability: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include_result: Optional[bool] = None,
    ) -> JSON:
        """Run history, newest first, as short summaries."""
        return self._request(
            "GET",
            "/v1/runs",
            params={
                "status": status,
                "capability": capability,
                "limit": limit,
                "cursor": cursor,
                "includeResult": include_result,
            },
        )

    def cancel_run(self, run_id: str) -> JSON:
        """Cancels a queued or running run."""
        return self._request("POST", f"/v1/runs/{_path(run_id)}/cancel")

    def run_attempts(self, run_id: str) -> JSON:
        """Every attempt for a run with its receipt and cost."""
        return self._request("GET", f"/v1/runs/{_path(run_id)}/attempts")

    def balance(self) -> JSON:
        """Available and reserved balance, minimum top-up and a payment link. Needs usage.read."""
        return self._request("GET", "/v1/balance")

    # ---- transport ----

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Mapping[str, Any]] = None,
        auth: bool = True,
    ) -> Any:
        headers: Dict[str, str] = {}
        if auth:
            if not self._token:
                raise LoootError(
                    401, "missing_token", f"{method} {path} needs a token: set LOOOT_TOKEN or pass token="
                )
            headers["authorization"] = f"Bearer {self._token}"
        response = self._http.request(method, path, params=_clean(params or {}), json=json, headers=headers)
        try:
            data: Any = response.json() if response.content else None
        except ValueError:
            data = response.text
        if response.is_error:
            err = data.get("error") if isinstance(data, dict) else None
            err = err if isinstance(err, dict) else {}
            raise LoootError(
                response.status_code,
                err.get("code") or f"http_{response.status_code}",
                err.get("message") or f"{method} {path} failed with HTTP {response.status_code}",
                err.get("requestId"),
                data,
            )
        return data


def _path(segment: str) -> str:
    """Percent-encodes one path segment."""
    from urllib.parse import quote

    return quote(segment, safe="")


__all__: List[str] = ["Looot", "DEFAULT_BASE_URL", "Prefer"]
