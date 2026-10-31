"""Offline tests for Looot: the 8 contract conformance tests, then every method's request."""

from __future__ import annotations

import httpx
import pytest

from conftest import make
from looot import DEFAULT_BASE_URL, Looot, LoootError, USER_AGENT, __version__

# ---- the 8 conformance tests from the SDK contract, section 12 ----


def test_1_catalog_overview_sends_topic_and_no_token():
    client, rec = make(httpx.Response(200, json={"revision": "1", "jobs": []}), token="abc")
    out = client.catalog_overview(topic="email")
    assert out["revision"] == "1"
    assert rec.last.url.path == "/v1/catalog/overview"
    assert rec.last.url.params["topic"] == "email"
    assert "authorization" not in rec.last.headers


def test_2_search_sends_bearer_maps_names_and_drops_unset():
    client, rec = make(httpx.Response(200, json={"endpoints": []}), token="abc")
    client.search("verify an email", prefer="cheapest", max_price_micros=5000, keyless=True)
    req = rec.last
    assert req.headers["authorization"] == "Bearer abc"
    assert dict(req.url.params) == {
        "q": "verify an email",
        "prefer": "cheapest",
        "maxPriceMicros": "5000",
        "keyless": "true",
    }


def test_3_token_route_without_token_raises_and_sends_nothing():
    client, rec = make(token=None)
    with pytest.raises(LoootError) as info:
        client.balance()
    err = info.value
    assert (err.status, err.code) == (401, "missing_token")
    assert err.message == "GET /v1/balance needs a token: set LOOOT_TOKEN or pass token"
    assert err.retryable is False
    assert rec.requests == []


def test_4_run_job_posts_job_id_wait_in_query_and_prefer_in_fallback():
    client, rec = make(httpx.Response(201, json={"runId": "run_1", "status": "completed"}))
    run = client.run_job(
        "people.email.verify",
        {"email": "jane.doe@example.com"},
        prefer="cheapest",
        fallback={"maxAttempts": 3},
        wait=20,
        idempotency_key="k1",
    )
    assert run["runId"] == "run_1"
    assert rec.last.method == "POST"
    assert rec.last.url.path == "/v1/runs"
    assert rec.last.url.params["wait"] == "20"
    assert rec.body() == {
        "endpointId": "job:people.email.verify",
        "input": {"email": "jane.doe@example.com"},
        "idempotencyKey": "k1",
        "fallback": {"maxAttempts": 3, "prefer": "cheapest"},
    }


def test_5_run_keeps_explicit_fallback_and_generates_sdk_key():
    client, rec = make(httpx.Response(201, json={"runId": "r", "status": "queued"}))
    client.run(
        "icypeas-email-verify",
        {"email": "jane.doe@example.com"},
        fallback={"maxAttempts": 2, "maxCostUsd": 0.05},
    )
    body = rec.body()
    assert body["fallback"] == {"maxAttempts": 2, "maxCostUsd": 0.05}
    assert body["idempotencyKey"].startswith("sdk-")
    assert len(body["idempotencyKey"]) == len("sdk-") + 36
    assert "wait" not in rec.last.url.params


def test_6_402_becomes_looot_error_with_code_request_id_and_top_up():
    client, _ = make(
        httpx.Response(
            402,
            json={
                "error": {"code": "insufficient_balance", "message": "Top up", "requestId": "req_1"},
                "topUp": {
                    "checkoutUrl": None,
                    "dashboardUrl": "https://looot.ai/usage?top_up=1",
                    "minimumUsd": 5,
                },
            },
        )
    )
    with pytest.raises(LoootError) as info:
        client.run("x", {})
    err = info.value
    assert (err.status, err.code, err.request_id) == (402, "insufficient_balance", "req_1")
    assert err.retryable is False
    assert err.top_up is not None
    assert err.top_up.url == "https://looot.ai/usage?top_up=1"
    assert err.top_up.minimum_usd == 5
    assert "new idempotency key" in (err.retry_hint or "")


def test_7_201_failed_run_is_returned_not_raised():
    failed = {
        "runId": "run_2",
        "status": "failed",
        "outcome": "rejected",
        "result": {"code": "unknown_job"},
        "error": {"code": "validation_error", "message": "Unknown job", "retryable": False},
    }
    client, _ = make(httpx.Response(201, json=failed))
    run = client.run_job("nope.nope", {})
    assert run["status"] == "failed"
    assert run["error"]["code"] == "validation_error"


def test_8_path_segments_are_encoded():
    client, rec = make(httpx.Response(200, json={"runId": "a/b"}))
    client.get_run("a/b")
    assert rec.last.url.raw_path == b"/v1/runs/a%2Fb"
    client.inspect("job:people.email.find")
    assert rec.last.url.raw_path == b"/v1/operations/job%3Apeople.email.find"


# ---- every method sends the right request ----

ITEM = "icypeas-email-verify"
EMAIL = {"email": "jane.doe@example.com"}
NAME = {"name": "Jane Doe", "domain": "example.com"}

# (name, call, HTTP method, path, query, JSON body or None, sends the token)
CASES = [
    (
        "catalog_overview",
        lambda c: c.catalog_overview(depth="jobs", category="enrichment"),
        "GET", "/v1/catalog/overview", {"depth": "jobs", "category": "enrichment"}, None, False,
    ),
    (
        "public_catalog",
        lambda c: c.public_catalog(
            capability="people_email_verify", text="verify", operation_id="op", limit=1, cursor="c1"
        ),
        "GET", "/v1/public-catalog",
        {"capability": "people_email_verify", "text": "verify", "operationId": "op", "limit": "1", "cursor": "c1"},
        None, False,
    ),
    (
        "public_catalog_item",
        lambda c: c.public_catalog_item(ITEM),
        "GET", f"/v1/public-catalog/{ITEM}", {}, None, False,
    ),
    (
        "compare_public_catalog",
        lambda c: c.compare_public_catalog(["a-one", "b-two"]),
        "POST", "/v1/public-catalog/compare", {}, {"catalogItemIds": ["a-one", "b-two"]}, False,
    ),
    (
        "search",
        lambda c: c.search("email", limit=5, offset=5, capability="people.email.find", verified=False),
        "GET", "/v1/catalog/search",
        {"q": "email", "limit": "5", "offset": "5", "capability": "people.email.find", "verified": "false"},
        None, True,
    ),
    (
        "discover",
        lambda c: c.discover("find a work email", prefer="reliable", result_limit=3, endpoint_id="e1"),
        "GET", "/v1/discover",
        {"query": "find a work email", "prefer": "reliable", "resultLimit": "3", "endpointId": "e1"},
        None, True,
    ),
    (
        "catalog_endpoints",
        lambda c: c.catalog_endpoints(limit=100, facets=True, max_price_micros=1000),
        "GET", "/v1/catalog/endpoints", {"limit": "100", "facets": "true", "maxPriceMicros": "1000"}, None, True,
    ),
    ("inspect", lambda c: c.inspect(ITEM), "GET", f"/v1/operations/{ITEM}", {}, None, True),
    (
        "run",
        lambda c: c.run(ITEM, EMAIL, idempotency_key="k", wait=True, output={"format": "json"}),
        "POST", "/v1/runs", {"wait": "true"},
        {"endpointId": ITEM, "input": EMAIL, "idempotencyKey": "k", "output": {"format": "json"}},
        True,
    ),
    (
        "run_job",
        lambda c: c.run_job("people.email.find", NAME, fallback=True, idempotency_key="k"),
        "POST", "/v1/runs", {},
        {"endpointId": "job:people.email.find", "input": NAME, "idempotencyKey": "k", "fallback": True},
        True,
    ),
    (
        "get_run",
        lambda c: c.get_run("run_1", fields=["emails", "person.name"], max_items=10),
        "GET", "/v1/runs/run_1", {"fields": "emails,person.name", "max_items": "10"}, None, True,
    ),
    (
        "list_runs",
        lambda c: c.list_runs(status="completed", limit=5, include_result=True),
        "GET", "/v1/runs", {"status": "completed", "limit": "5", "includeResult": "true"}, None, True,
    ),
    ("cancel_run", lambda c: c.cancel_run("run_1"), "POST", "/v1/runs/run_1/cancel", {}, None, True),
    ("run_attempts", lambda c: c.run_attempts("run_1"), "GET", "/v1/runs/run_1/attempts", {}, None, True),
    ("balance", lambda c: c.balance(), "GET", "/v1/balance", {}, None, True),
    ("list_top_ups", lambda c: c.list_top_ups(), "GET", "/v1/top-ups", {}, None, True),
    ("ledger", lambda c: c.ledger(limit=50, cursor="c"), "GET", "/v1/ledger", {"limit": "50", "cursor": "c"}, None, True),
    ("whoami", lambda c: c.whoami(), "GET", "/v1/whoami", {}, None, True),
    (
        "capability_request",
        lambda c: c.capability_request(
            "Find a phone", "Phone from a LinkedIn URL", desired_inputs=["linkedinUrl"], idempotency_key="req-phone-1"
        ),
        "POST", "/v1/capability-requests", {},
        {
            "requestId": "req-phone-1",
            "title": "Find a phone",
            "description": "Phone from a LinkedIn URL",
            "idempotencyKey": "req-phone-1",
            "desiredInputs": ["linkedinUrl"],
        },
        True,
    ),
]
TOKEN_CASES = [c for c in CASES if c[6]]


@pytest.mark.parametrize("name,call,method,path,query,body,auth", CASES, ids=[c[0] for c in CASES])
def test_method_request(name, call, method, path, query, body, auth):
    client, rec = make(httpx.Response(200, json={"ok": True}), token="abc")
    assert call(client) == {"ok": True}
    req = rec.last
    assert req.method == method
    assert req.url.path == path
    assert dict(req.url.params) == query
    assert req.headers["accept"] == "application/json"
    assert req.headers["user-agent"] == USER_AGENT
    if body is None:
        assert req.content == b""
        assert "content-type" not in req.headers
    else:
        assert rec.body() == body
        assert req.headers["content-type"] == "application/json"
    if auth:
        assert req.headers["authorization"] == "Bearer abc"
    else:
        assert "authorization" not in req.headers


@pytest.mark.parametrize("name,call,method,path,query,body,auth", TOKEN_CASES, ids=[c[0] for c in TOKEN_CASES])
def test_every_token_method_refuses_without_token(name, call, method, path, query, body, auth):
    client, rec = make(token=None)
    with pytest.raises(LoootError) as info:
        call(client)
    assert info.value.code == "missing_token"
    assert rec.requests == []


def test_run_job_without_prefer_or_fallback_sends_no_fallback():
    client, rec = make(httpx.Response(201, json={"status": "queued"}))
    client.run_job("people.email.find", NAME)
    assert "fallback" not in rec.body()


def test_run_job_prefer_with_fallback_true_sends_prefer_object():
    client, rec = make(httpx.Response(201, json={"status": "queued"}))
    client.run_job("people.email.find", NAME, prefer="reliable", fallback=True)
    assert rec.body()["fallback"] == {"prefer": "reliable"}


def test_run_job_passes_output():
    client, rec = make(httpx.Response(201, json={"status": "queued"}))
    client.run_job("web.scrape.markdown", {"url": "https://example.com"}, output={"format": "markdown"})
    assert rec.body()["output"] == {"format": "markdown"}


def test_run_returns_open_dict_with_unknown_fields():
    client, _ = make(httpx.Response(201, json={"runId": "r", "status": "brand_new_status", "extra": 1}))
    run = client.run(ITEM, EMAIL)
    assert run["status"] == "brand_new_status"
    assert run["extra"] == 1


def test_capability_request_generates_one_key_for_both_ids():
    client, rec = make(httpx.Response(201, json={}))
    client.capability_request("t", "d")
    body = rec.body()
    assert body["idempotencyKey"].startswith("sdk-")
    assert body["requestId"] == body["idempotencyKey"]


def test_download_media_returns_bytes_and_type():
    client, rec = make(httpx.Response(200, content=b"%PDF-1", headers={"content-type": "application/pdf"}))
    media = client.download_media("/v1/runs/run_1/media/m1")
    assert media.content == b"%PDF-1"
    assert media.content_type == "application/pdf"
    assert rec.last.headers["authorization"] == "Bearer t"
    client.download_media(DEFAULT_BASE_URL + "/v1/runs/run_1/media/m1")
    assert rec.last.url.path == "/v1/runs/run_1/media/m1"


def test_download_media_refuses_other_hosts():
    client, rec = make()
    with pytest.raises(ValueError):
        client.download_media("https://evil.example.com/v1/runs/run_1/media/m1")
    assert rec.requests == []


def test_wait_for_run_polls_until_terminal_with_backoff():
    sleeps: list = []
    client, rec = make(
        httpx.Response(200, json={"runId": "r", "status": "queued"}),
        httpx.Response(200, json={"runId": "r", "status": "running"}),
        httpx.Response(200, json={"runId": "r", "status": "completed", "outcome": "hit"}),
        sleeps=sleeps,
    )
    run = client.wait_for_run("r", interval=1, max_interval=5)
    assert run["status"] == "completed"
    assert len(rec.requests) == 3
    assert sleeps == [1, 1.5]


def test_wait_for_run_times_out_with_last_run():
    client, _ = make(httpx.Response(200, json={"runId": "r", "status": "running"}))
    with pytest.raises(LoootError) as info:
        client.wait_for_run("r", timeout=0, interval=1)
    assert info.value.code == "wait_timeout"
    assert info.value.body["status"] == "running"


def test_iter_runs_follows_cursor():
    client, rec = make(
        httpx.Response(200, json={"runs": [{"runId": "a"}, {"runId": "b"}], "nextCursor": "c2"}),
        httpx.Response(200, json={"runs": [{"runId": "c"}], "nextCursor": None}),
    )
    assert [r["runId"] for r in client.iter_runs(limit=2)] == ["a", "b", "c"]
    assert "cursor" not in rec.requests[0].url.params
    assert rec.requests[1].url.params["cursor"] == "c2"


def test_iter_public_catalog_follows_cursor_without_token():
    client, rec = make(
        httpx.Response(200, json={"items": [{"catalogItemId": "a"}], "nextCursor": "n"}),
        httpx.Response(200, json={"items": [{"catalogItemId": "b"}], "nextCursor": None}),
        token=None,
    )
    ids = [i["catalogItemId"] for i in client.iter_public_catalog(capability="people_email_verify")]
    assert ids == ["a", "b"]
    assert rec.requests[1].url.params["cursor"] == "n"


def test_iter_search_follows_offset():
    client, rec = make(
        httpx.Response(200, json={"endpoints": [{"endpointId": "a"}], "nextOffset": 1}),
        httpx.Response(200, json={"endpoints": [{"endpointId": "b"}], "nextOffset": None}),
    )
    assert [r["endpointId"] for r in client.iter_search("email", limit=1)] == ["a", "b"]
    assert rec.requests[1].url.params["offset"] == "1"


# ---- configuration ----


def test_token_from_env_then_api_key_alias(monkeypatch):
    monkeypatch.setenv("LOOOT_API_KEY", " key2 ")
    client, rec = make(token=None)
    client.balance()
    assert rec.last.headers["authorization"] == "Bearer key2"
    monkeypatch.setenv("LOOOT_TOKEN", "  tok1\n")
    client, rec = make(token=None)
    client.balance()
    assert rec.last.headers["authorization"] == "Bearer tok1"


def test_explicit_empty_token_does_not_fall_back_to_env(monkeypatch):
    monkeypatch.setenv("LOOOT_TOKEN", "tok1")
    client, rec = make(token="")
    with pytest.raises(LoootError):
        client.balance()
    assert rec.requests == []


def test_sdk_ignores_looot_api_url(monkeypatch):
    monkeypatch.setenv("LOOOT_API_URL", "http://127.0.0.1:9999")
    client, rec = make()
    client.balance()
    assert str(rec.last.url) == "https://api.looot.ai/v1/balance"


def test_base_url_override_strips_trailing_slash():
    client, rec = make(base_url="http://127.0.0.1:8787///")
    client.balance()
    assert str(rec.last.url) == "http://127.0.0.1:8787/v1/balance"


def test_agent_header_only_when_set():
    client, rec = make(agent="n8n")
    client.balance()
    assert rec.last.headers["x-looot-agent"] == "n8n"
    client, rec = make()
    client.balance()
    assert "x-looot-agent" not in rec.last.headers
    with pytest.raises(ValueError):
        Looot("t", agent="x" * 65)


def test_user_agent_and_version():
    assert USER_AGENT.startswith(f"looot-python/{__version__} python/")


def test_timeout_default_and_override():
    assert Looot("t")._http.timeout.read == 75.0
    assert Looot("t", timeout=5)._http.timeout.read == 5.0


def test_token_never_in_repr_or_error():
    client, _ = make(
        httpx.Response(401, json={"error": {"code": "unauthorized", "message": "Bad token"}}),
        token="not-a-real-token-SECRETVALUE",
    )
    assert "SECRETVALUE" not in repr(client)
    with pytest.raises(LoootError) as info:
        client.balance()
    assert "SECRETVALUE" not in str(info.value) + repr(info.value)


def test_context_manager_closes():
    client, _ = make()
    with client as c:
        assert c is client
    assert client._http.is_closed
