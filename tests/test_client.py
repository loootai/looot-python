"""Offline tests: httpx.MockTransport answers every request, nothing leaves the machine."""

import json

import httpx
import pytest

from looot import Looot, LoootError


def make_client(status=200, payload=None, token="t"):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json=payload if payload is not None else {})

    return Looot(token, transport=httpx.MockTransport(handler)), calls


def test_catalog_overview_sends_no_token():
    client, calls = make_client(payload={"revision": "1"})
    client.catalog_overview(topic="email")
    assert calls[0].url.path == "/v1/catalog/overview"
    assert calls[0].url.params["topic"] == "email"
    assert "authorization" not in calls[0].headers


def test_search_sends_bearer_and_maps_names():
    client, calls = make_client(payload={"endpoints": []}, token="abc")
    client.search("verify an email", prefer="cheapest", max_price_micros=5000, keyless=True)
    req = calls[0]
    assert req.headers["authorization"] == "Bearer abc"
    assert req.url.params["maxPriceMicros"] == "5000"
    assert req.url.params["keyless"] == "true"
    assert "limit" not in req.url.params


def test_token_route_without_token_raises_before_sending(monkeypatch):
    monkeypatch.delenv("LOOOT_TOKEN", raising=False)
    client, calls = make_client(token=None)
    with pytest.raises(LoootError) as info:
        client.balance()
    assert info.value.code == "missing_token"
    assert calls == []


def test_run_job_body():
    client, calls = make_client(status=201, payload={"runId": "run_1", "status": "completed"})
    run = client.run_job(
        "people.email.verify",
        {"email": "jane.doe@example.com"},
        prefer="cheapest",
        fallback={"maxAttempts": 3},
        wait=20,
        idempotency_key="k1",
    )
    assert run["runId"] == "run_1"
    req = calls[0]
    assert req.method == "POST"
    assert req.url.params["wait"] == "20"
    assert json.loads(req.content) == {
        "endpointId": "job:people.email.verify",
        "input": {"email": "jane.doe@example.com"},
        "idempotencyKey": "k1",
        "fallback": {"maxAttempts": 3, "prefer": "cheapest"},
    }


def test_run_generates_idempotency_key():
    client, calls = make_client(status=201, payload={"runId": "r", "status": "queued"})
    client.run("icypeas-email-verify", {"email": "jane.doe@example.com"})
    assert json.loads(calls[0].content)["idempotencyKey"].startswith("sdk-")


def test_error_body_becomes_looot_error():
    client, _ = make_client(
        status=402,
        payload={"error": {"code": "insufficient_balance", "message": "Top up", "requestId": "req_1"}},
    )
    with pytest.raises(LoootError) as info:
        client.run("x", {})
    assert info.value.status == 402
    assert info.value.code == "insufficient_balance"
    assert info.value.request_id == "req_1"
