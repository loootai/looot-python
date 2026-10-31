"""Looot, the synchronous client for the looot REST API.

scripts/gen_async.py writes _async_client.py (AsyncLooot) from this file. Edit this file, then
run ``python scripts/gen_async.py``. tests/test_async.py fails when the two drift apart.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Union

import httpx

from ._core import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    build_call,
    check_agent,
    default_headers,
    new_idempotency_key,
    read_response,
    resolve_token,
    retry_delay,
    segment,
    transport_error,
)
from ._errors import LoootError
from ._types import (
    TERMINAL_STATUSES,
    JSON,
    Balance,
    CapabilityRequest,
    CatalogEndpointsPage,
    CatalogOverview,
    DiscoverResult,
    Fallback,
    MediaDownload,
    Operation,
    OverviewDepth,
    Prefer,
    PublicCatalogItem,
    PublicCatalogPage,
    Run,
    RunAttempts,
    RunList,
    RunSummary,
    SearchResult,
    SearchRow,
    TopUps,
)

Wait = Union[int, float, bool, None]


class Looot:
    """Synchronous client for the looot REST API.

    Args:
        token: an agent token (``cs_ms_...``) or a dashboard API key. Defaults to the
            ``LOOOT_TOKEN`` environment variable, then ``LOOOT_API_KEY``. The free catalog
            routes work without one.
        base_url: defaults to ``https://api.looot.ai``.
        timeout: seconds per request, 75 by default (enough for ``wait=60``).
        max_retries: retries for 429, retryable 503s, one 500, network failures and
            timeouts. 2 by default, 0 turns them off. Retries reuse the same idempotency key.
        agent: your app or agent name, sent as ``X-Looot-Agent`` for usage analytics.
        transport: an httpx transport, for tests.
        sleep: replaces the sleep between retries and polls, for tests.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        agent: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
        sleep: Optional[Callable[[float], Any]] = None,
    ) -> None:
        self._token = resolve_token(token)
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(0, int(max_retries))
        self._sleep = sleep or time.sleep
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers=default_headers(check_agent(agent)),
        )

    def __repr__(self) -> str:
        token = "set" if self._token else "none"
        return f"{type(self).__name__}(base_url={self.base_url!r}, token={token})"

    # ---- lifecycle ----

    def close(self) -> None:
        """Closes the HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "Looot":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- catalog, free and public ----

    def catalog_overview(
        self,
        *,
        depth: Optional[OverviewDepth] = None,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> CatalogOverview:
        """Free, no token. Categories, platforms and jobs with counts and cheapest prices.

        ``topic`` returns the matching jobs (at most 25), each with its job id.
        """
        return self._send(
            "GET",
            "/v1/catalog/overview",
            params={"depth": depth, "category": category, "platform": platform, "topic": topic},
            auth=False,
        )

    def public_catalog(
        self,
        *,
        q: Optional[str] = None,
        text: Optional[str] = None,
        capability: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        operation_id: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> PublicCatalogPage:
        """Free, no token. Published items with their parameters and price.

        ``capability`` is the job id with dots turned into underscores (``people_email_verify``).
        ``limit`` is 1 to 100. Follow ``nextCursor`` until it is None.
        """
        return self._send(
            "GET",
            "/v1/public-catalog",
            params={
                "q": q,
                "text": text,
                "capability": capability,
                "category": category,
                "provider": provider,
                "operationId": operation_id,
                "limit": limit,
                "cursor": cursor,
            },
            auth=False,
        )

    def public_catalog_item(self, catalog_item_id: str) -> PublicCatalogItem:
        """Free, no token. One published catalog item."""
        return self._send("GET", f"/v1/public-catalog/{segment(catalog_item_id)}", auth=False)

    def compare_public_catalog(self, catalog_item_ids: Sequence[str]) -> JSON:
        """Free, no token. Compares 2 to 20 public catalog items side by side."""
        return self._send(
            "POST",
            "/v1/public-catalog/compare",
            body={"catalogItemIds": list(catalog_item_ids)},
            auth=False,
        )

    # ---- catalog, token ----

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
    ) -> SearchResult:
        """Free, needs ``catalog.read``. Ranked search across every provider.

        ``capability`` is a job id with dots (``people.email.find``). Rows are in
        ``["endpoints"]``. Follow ``nextOffset`` until it is None.
        """
        return self._send(
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

    def discover(
        self,
        query: Optional[str] = None,
        *,
        mode: Optional[str] = None,
        prefer: Optional[Prefer] = None,
        capability: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        endpoint_id: Optional[str] = None,
        max_price: Optional[float] = None,
        minimum_score: Optional[float] = None,
        result_limit: Optional[int] = None,
        detail: Optional[str] = None,
    ) -> DiscoverResult:
        """Free, needs ``catalog.read``. Up to 5 scored candidates for a task."""
        return self._send(
            "GET",
            "/v1/discover",
            params={
                "query": query,
                "mode": mode,
                "prefer": prefer,
                "capability": capability,
                "category": category,
                "provider": provider,
                "endpointId": endpoint_id,
                "maxPrice": max_price,
                "minimumScore": minimum_score,
                "resultLimit": result_limit,
                "detail": detail,
            },
        )

    def catalog_endpoints(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        provider: Optional[str] = None,
        capability: Optional[str] = None,
        keyless: Optional[bool] = None,
        verified: Optional[bool] = None,
        max_price_micros: Optional[int] = None,
        facets: Optional[bool] = None,
    ) -> CatalogEndpointsPage:
        """Free, needs ``catalog.read``. The full catalog, cursor paged. ``facets=True`` adds counts."""
        return self._send(
            "GET",
            "/v1/catalog/endpoints",
            params={
                "limit": limit,
                "cursor": cursor,
                "category": category,
                "platform": platform,
                "provider": provider,
                "capability": capability,
                "keyless": keyless,
                "verified": verified,
                "maxPriceMicros": max_price_micros,
                "facets": facets,
            },
        )

    def inspect(self, endpoint_id: str) -> Operation:
        """Free, needs a token. Input schema, price formula and the most a run can cost.

        Takes an endpoint id, not ``job:<id>``.
        """
        return self._send("GET", f"/v1/operations/{segment(endpoint_id)}")

    # ---- runs ----

    def run(
        self,
        endpoint_id: str,
        input: Mapping[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        wait: Wait = None,
        fallback: Optional[Fallback] = None,
        output: Optional[Mapping[str, Any]] = None,
    ) -> Run:
        """Paid, needs ``runs.execute``. Holds the estimated cost, runs, settles.

        A returned run is not success: read ``run["status"]``, ``run["outcome"]`` and
        ``run["error"]``. A failed run comes back as a run, it does not raise.

        ``idempotency_key`` is generated (``sdk-<uuid>``) when omitted. Build your own from
        your record (``lead-4821-email``) so a crashed worker replays instead of paying twice.
        ``wait`` is seconds (0 to 60) or True for 20 s. Without it the run comes back queued.
        """
        body: Dict[str, Any] = {
            "endpointId": endpoint_id,
            "input": dict(input),
            "idempotencyKey": idempotency_key or new_idempotency_key(),
        }
        if fallback is not None:
            body["fallback"] = fallback if isinstance(fallback, bool) else dict(fallback)
        if output is not None:
            body["output"] = dict(output)
        return self._send("POST", "/v1/runs", params={"wait": wait}, body=body)

    def run_job(
        self,
        job: str,
        input: Mapping[str, Any],
        *,
        prefer: Optional[Prefer] = None,
        fallback: Optional[Fallback] = None,
        wait: Wait = None,
        idempotency_key: Optional[str] = None,
        output: Optional[Mapping[str, Any]] = None,
    ) -> Run:
        """Paid. Runs a job (``endpointId: "job:<id>"``) and looot picks the provider.

        ``prefer`` goes into ``fallback.prefer``, which turns fallback on. Without ``prefer``
        and ``fallback`` a job run does not fall back. Take job ids from
        ``catalog_overview(topic=...)`` or a search row's ``capability``.
        """
        fb: Optional[Fallback] = fallback
        if prefer is not None:
            fb = {**fallback, "prefer": prefer} if isinstance(fallback, Mapping) else {"prefer": prefer}
        return self.run(
            f"job:{job}",
            input,
            idempotency_key=idempotency_key,
            wait=wait,
            fallback=fb,
            output=output,
        )

    def get_run(
        self,
        run_id: str,
        *,
        fields: Optional[Sequence[str]] = None,
        max_items: Optional[int] = None,
    ) -> Run:
        """Free, needs ``runs.read``. One run with its status, result, cost and error.

        ``fields`` keeps only these dotted paths of ``result``; ``max_items`` caps every list.
        """
        return self._send(
            "GET",
            f"/v1/runs/{segment(run_id)}",
            params={"fields": ",".join(fields) if fields else None, "max_items": max_items},
        )

    def wait_for_run(
        self,
        run_id: str,
        *,
        timeout: float = 300.0,
        interval: float = 1.0,
        max_interval: float = 5.0,
    ) -> Run:
        """Polls ``get_run`` until the run reaches a terminal status, then returns it.

        Starts at ``interval`` seconds and backs off to ``max_interval``. Raises
        ``LoootError`` with code ``wait_timeout`` (and the last run in ``body``) after
        ``timeout`` seconds.
        """
        deadline = time.monotonic() + timeout
        delay = interval
        while True:
            run = self.get_run(run_id)
            if run.get("status") in TERMINAL_STATUSES:
                return run
            if time.monotonic() + delay > deadline:
                raise LoootError(
                    0,
                    "wait_timeout",
                    f"run {run_id} is still {run.get('status')} after {timeout:g} s",
                    body=run,
                    retryable=True,
                    retry_hint="Call wait_for_run again, or read the run later with get_run.",
                )
            self._sleep(delay)
            delay = min(delay * 1.5, max_interval)

    def list_runs(
        self,
        *,
        status: Optional[str] = None,
        capability: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        include_result: Optional[bool] = None,
    ) -> RunList:
        """Free, needs ``runs.read``. Run history, newest first. ``limit`` is 1 to 50."""
        return self._send(
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

    def cancel_run(self, run_id: str) -> Run:
        """Free, needs ``runs.execute``. Cancels a queued or running run.

        A settled run comes back unchanged, never an error.
        """
        return self._send("POST", f"/v1/runs/{segment(run_id)}/cancel")

    def run_attempts(self, run_id: str) -> RunAttempts:
        """Free, needs ``runs.read``. Every provider attempt with its status, latency and cost."""
        return self._send("GET", f"/v1/runs/{segment(run_id)}/attempts")

    def download_media(self, download_path: str) -> MediaDownload:
        """Free, needs a token. Downloads a run's stored file from ``result.media.downloadPath``.

        Accepts the path (``/v1/...``) or a full URL on this client's base URL. Any other host
        is refused, so the token never leaves for a third party.
        """
        path = download_path
        if path.startswith(self.base_url + "/"):
            path = path[len(self.base_url) :]
        if not path.startswith("/v1/"):
            raise ValueError("download_path must be a /v1/ path on the looot API")
        response = self._send("GET", path, raw=True)
        return MediaDownload(response.content, response.headers.get("content-type", ""))

    # ---- money and account ----

    def balance(self) -> Balance:
        """Free, needs ``usage.read``. Available and reserved USD, and ``topUpLink``.

        Show the user ``topUpLink["checkoutUrl"]`` when set, else ``topUpLink["dashboardUrl"]``.
        """
        return self._send("GET", "/v1/balance")

    def list_top_ups(self) -> TopUps:
        """Free, needs ``usage.read``. Past top-ups."""
        return self._send("GET", "/v1/top-ups")

    def ledger(self, *, limit: Optional[int] = None, cursor: Optional[str] = None) -> JSON:
        """Free, needs ``usage.read``. Ledger entries: holds, charges, releases and top-ups."""
        return self._send("GET", "/v1/ledger", params={"limit": limit, "cursor": cursor})

    def whoami(self) -> JSON:
        """Free, needs ``organizations.read``. The token's organization and membership."""
        return self._send("GET", "/v1/whoami")

    def capability_request(
        self,
        title: str,
        description: str,
        *,
        desired_inputs: Optional[Sequence[str]] = None,
        desired_outputs: Optional[Sequence[str]] = None,
        request_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> CapabilityRequest:
        """Free, needs a token. Asks looot for a provider or job the catalog lacks."""
        key = idempotency_key or new_idempotency_key()
        body: Dict[str, Any] = {
            "requestId": request_id or key,
            "title": title,
            "description": description,
            "idempotencyKey": key,
        }
        if desired_inputs is not None:
            body["desiredInputs"] = list(desired_inputs)
        if desired_outputs is not None:
            body["desiredOutputs"] = list(desired_outputs)
        return self._send("POST", "/v1/capability-requests", body=body)

    # ---- pagination ----

    def iter_runs(
        self,
        *,
        status: Optional[str] = None,
        capability: Optional[str] = None,
        limit: Optional[int] = None,
        include_result: Optional[bool] = None,
    ) -> Iterator[RunSummary]:
        """Every run, newest first, following ``nextCursor`` until it is None."""
        cursor: Optional[str] = None
        while True:
            page = self.list_runs(
                status=status,
                capability=capability,
                limit=limit,
                cursor=cursor,
                include_result=include_result,
            )
            for item in page.get("runs") or []:
                yield item
            cursor = page.get("nextCursor")
            if not cursor:
                return

    def iter_public_catalog(
        self,
        *,
        q: Optional[str] = None,
        capability: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[PublicCatalogItem]:
        """Every public catalog item that matches, following ``nextCursor``."""
        cursor: Optional[str] = None
        while True:
            page = self.public_catalog(
                q=q,
                capability=capability,
                category=category,
                provider=provider,
                limit=limit,
                cursor=cursor,
            )
            for item in page.get("items") or []:
                yield item
            cursor = page.get("nextCursor")
            if not cursor:
                return

    def iter_search(
        self,
        q: Optional[str] = None,
        *,
        limit: Optional[int] = None,
        capability: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        prefer: Optional[Prefer] = None,
    ) -> Iterator[SearchRow]:
        """Every search row, following ``nextOffset`` until it is None."""
        offset: Optional[int] = None
        while True:
            page = self.search(
                q,
                limit=limit,
                offset=offset,
                capability=capability,
                category=category,
                provider=provider,
                prefer=prefer,
            )
            for item in page.get("endpoints") or []:
                yield item
            offset = page.get("nextOffset")
            if offset is None:
                return

    # ---- transport ----

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        body: Optional[Mapping[str, Any]] = None,
        auth: bool = True,
        raw: bool = False,
    ) -> Any:
        call = build_call(method, path, token=self._token, params=params, body=body, auth=auth, raw=raw)
        attempt = 0
        while True:
            try:
                response = self._http.request(
                    call.method, call.path, params=call.params, content=call.content, headers=call.headers
                )
                return read_response(call, response)
            except LoootError as error:
                delay = retry_delay(error, attempt, self.max_retries)
                if delay is None:
                    raise
            except httpx.TransportError as exc:
                error = transport_error(call, exc)
                delay = retry_delay(error, attempt, self.max_retries)
                if delay is None:
                    raise error from exc
            self._sleep(delay)
            attempt += 1


__all__: List[str] = ["Looot"]
