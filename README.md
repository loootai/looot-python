# looot for Python

A small client for the [looot](https://looot.ai) REST API, built on `httpx`. looot is one
gateway to about 2,500 data provider operations (email find and verify, company enrichment,
SEO and SERP data, social profiles, web scraping) with one token, one prepaid balance and one
run contract.

Written by hand from the public OpenAPI at https://api.looot.ai/openapi.json. Methods return
the decoded JSON as plain dicts, so new gateway fields show up without an SDK release.

> Status: public, MIT. The PyPI name `looot` is free; the first release is not uploaded yet,
> so install from GitHub until then.

## Install

```bash
pip install git+https://github.com/loootai/looot-python    # until the PyPI release
```

Python 3.9+. One runtime dependency: `httpx==0.28.1`.

## 60-second quickstart

Browsing is free and needs no token:

```python
from looot import Looot

with Looot() as looot:
    for job in looot.catalog_overview(topic="email")["jobs"]:
        print(job["id"], job["providerCount"], job["cheapestPerCall"])
```

Search, inspect and run need an agent token. Create one at looot.ai (Settings, Agent tokens)
and export it as `LOOOT_TOKEN`:

```python
with Looot() as looot:
    found = looot.search("verify an email", prefer="cheapest")
    spec = looot.inspect(found["endpoints"][0]["endpointId"])

    # Paid. Top up first: looot.balance() shows the minimum.
    run = looot.run_job(
        "people.email.verify",
        {"email": "jane.doe@example.com"},
        prefer="cheapest",
        fallback={"maxAttempts": 3, "maxCostUsd": 0.05},
        wait=30,
    )
    if run["status"] == "completed":
        print(run.get("outcome"), run.get("normalized"), run.get("actualCost"))
    else:
        print(run["status"], run.get("error"))
```

## Methods

| Method | Route | Token | Cost |
| --- | --- | --- | --- |
| `catalog_overview(depth=, category=, platform=, topic=)` | `GET /v1/catalog/overview` | no | free |
| `public_catalog(q=, capability=, category=, provider=, limit=, cursor=)` | `GET /v1/public-catalog` | no | free |
| `public_catalog_item(id)` | `GET /v1/public-catalog/{id}` | no | free |
| `search(q, capability=, prefer=, max_price_micros=, ...)` | `GET /v1/catalog/search` | yes | free |
| `inspect(endpoint_id)` | `GET /v1/operations/{id}` | yes | free |
| `run(endpoint_id, input, idempotency_key=, wait=, fallback=)` | `POST /v1/runs` | yes | paid |
| `run_job(job, input, prefer=, fallback=, wait=)` | `POST /v1/runs` with `job:<id>` | yes | paid |
| `get_run(id)`, `list_runs(status=, capability=, limit=, cursor=)` | `GET /v1/runs...` | yes | free |
| `cancel_run(id)`, `run_attempts(id)` | `/v1/runs/{id}/cancel`, `/attempts` | yes | free |
| `balance()` | `GET /v1/balance` | yes (`usage.read`) | free |

The same rules as the REST API apply: a returned run is not success until `status` says
`completed`; pass your own `idempotency_key` to make retries safe; `wait` is seconds (0 to 60);
`prefer` is sent as `fallback.prefer` and turns fallback on. HTTP errors raise `LoootError`
with `status`, `code`, `request_id` and the raw `body`.

## Examples

```bash
python examples/overview.py                                     # free, no token
LOOOT_TOKEN=... python examples/search_and_inspect.py           # free, token
LOOOT_TOKEN=... python examples/runs_and_balance.py             # free, token
LOOOT_TOKEN=... python examples/run_job_with_fallback.py jane.doe@example.com   # PAID
```

## Develop

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock   # exact pins of the whole tree
.venv/bin/pip install --no-deps -e .             # the package itself, for the examples
.venv/bin/pytest                                 # offline tests (httpx.MockTransport)
.venv/bin/pytest -m live                         # free public routes only
bash scripts/leak-scan.sh .
git config core.hooksPath .githooks
```

## Links

- API reference: https://api.looot.ai/openapi.json
- Agent guide: https://api.looot.ai/llms.txt and https://api.looot.ai/llms-full.txt
- Docs: https://looot.ai/docs
- MCP server: https://api.looot.ai/mcp

## License

MIT. See [LICENSE](LICENSE).
