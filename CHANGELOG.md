# Changelog

## 0.1.0 (unreleased)

- First client: `catalog_overview`, `public_catalog`, `public_catalog_item`, `search`,
  `inspect`, `run`, `run_job` (`job:<id>`, `prefer`, `fallback`), `get_run`, `list_runs`,
  `cancel_run`, `run_attempts`, `balance`.
- `LoootError` maps the gateway's `{"error": {"code", "message", "requestId"}}` body.
- Dependencies pinned: `httpx==0.28.1`; dev tree in `requirements-dev.lock`.
