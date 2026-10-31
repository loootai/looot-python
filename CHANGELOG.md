# Changelog

## 0.2.0 (2026-10-31)

Brings the client to the looot SDK contract.

- `AsyncLooot`: the same methods as `Looot`, as coroutines, over `httpx.AsyncClient`.
- Typed responses: `Run`, `RunError`, `Route`, `Balance`, `SearchResult`, `CatalogOverview`,
  `PublicCatalogPage` and more, as `TypedDict`s that stay plain dicts at runtime.
- New methods: `discover`, `catalog_endpoints`, `compare_public_catalog`, `whoami`,
  `list_top_ups`, `ledger`, `capability_request`, `download_media`, `wait_for_run`,
  `iter_runs`, `iter_public_catalog`, `iter_search`.
- `run_job` takes `output`. `get_run` takes `fields` and `max_items`. `public_catalog` takes
  `text` and `operation_id`.
- Retries: 429, retryable 503s, one 500, network failures and timeouts, at most 2 times, with
  the same idempotency key. `max_retries=0` turns them off.
- `LoootError` gains `retryable`, `retry_hint`, `retry_after_seconds` and a typed `top_up` on
  a 402. Network failures and timeouts raise `LoootError` with status 0 instead of an httpx
  exception. `request_id` falls back to the `x-request-id` header.
- `User-Agent: looot-python/<version> python/<version>` on every request, and an `agent=`
  option that sends `X-Looot-Agent`.
- The token also reads from `LOOOT_API_KEY` when `LOOOT_TOKEN` is unset.
- Python 3.10 or newer (3.9 is past end of life). `httpx>=0.27,<1`.
- Built with hatchling, released to PyPI by a tag through trusted publishing (`PUBLISH.md`).
- Docs links point at https://docs.looot.ai/reference.

## 0.1.0 (2026-10-08)

- First client: `catalog_overview`, `public_catalog`, `public_catalog_item`, `search`,
  `inspect`, `run`, `run_job` (`job:<id>`, `prefer`, `fallback`), `get_run`, `list_runs`,
  `cancel_run`, `run_attempts`, `balance`.
- `LoootError` maps the gateway's `{"error": {"code", "message", "requestId"}}` body.
- Dependencies pinned: `httpx==0.28.1`; dev tree in `requirements-dev.lock`.
- MIT licence. Removed the `Private :: Do Not Upload` classifier.
