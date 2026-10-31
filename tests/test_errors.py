"""Error mapping, retry rules and transport failures."""

from __future__ import annotations

import httpx
import pytest

from conftest import make
from looot import LoootError


def err(status, code, **extra):
    body = {"error": {"code": code, "message": f"{code} happened", "requestId": "req_9"}}
    body.update(extra.pop("body", {}))
    return httpx.Response(status, json=body, **extra)


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (400, "validation_error", False),
        (400, "runs_cursor_invalid", False),
        (401, "unauthorized", False),
        (401, "token_revoked", False),
        (402, "key_spend_limit_reached", False),
        (403, "forbidden", False),
        (404, "not_found", False),
        (404, "unknown_category", False),
        (405, "method_not_allowed", False),
        (409, "idempotency_conflict", False),
        (409, "catalog_cursor_stale", False),
        (422, "rows_mode_unsupported", False),
        (429, "too_many_inflight_runs", True),
        (429, "run_rate_limited", True),
        (429, "rate_limit_exceeded", True),
        (500, "internal_error", True),
        (503, "catalog_loading", True),
        (503, "storage_busy", True),
        (503, "storage_uncertain", True),
        (503, "runtime_bridge_timeout", True),
        (503, "billing_unavailable", False),
    ],
)
def test_error_codes_map_to_retryable(status, code, retryable):
    client, _ = make(err(status, code), max_retries=0)
    with pytest.raises(LoootError) as info:
        client.balance()
    e = info.value
    assert (e.status, e.code, e.message, e.request_id) == (status, code, f"{code} happened", "req_9")
    assert e.retryable is retryable
    assert e.body["error"]["code"] == code


def test_error_without_envelope_uses_http_status_and_header_request_id():
    client, _ = make(
        httpx.Response(502, text="<html>bad gateway</html>", headers={"x-request-id": "req_hdr"}),
        max_retries=0,
    )
    with pytest.raises(LoootError) as info:
        client.balance()
    e = info.value
    assert e.code == "http_502"
    assert e.message == "GET /v1/balance failed with HTTP 502"
    assert e.request_id == "req_hdr"
    assert e.body == "<html>bad gateway</html>"
    assert e.retryable is True


def test_body_retryable_and_retry_hint_win_over_the_table():
    client, _ = make(
        err(400, "validation_error", body={"error": {"code": "validation_error", "message": "m", "retryable": True, "retryHint": "Say hi."}}),
        max_retries=0,
    )
    with pytest.raises(LoootError) as info:
        client.balance()
    assert info.value.retryable is True
    assert info.value.retry_hint == "Say hi."


def test_retry_after_from_body_then_header():
    client, _ = make(err(429, "run_rate_limited", body={"retryAfterSeconds": 7}), max_retries=0)
    with pytest.raises(LoootError) as info:
        client.balance()
    assert info.value.retry_after_seconds == 7
    client, _ = make(err(503, "storage_busy", headers={"retry-after": "3"}), max_retries=0)
    with pytest.raises(LoootError) as info:
        client.balance()
    assert info.value.retry_after_seconds == 3


def test_429_is_retried_with_the_same_idempotency_key():
    sleeps: list = []
    client, rec = make(
        err(429, "too_many_inflight_runs", headers={"retry-after": "2"}),
        httpx.Response(201, json={"runId": "r", "status": "queued"}),
        sleeps=sleeps,
    )
    run = client.run("icypeas-email-verify", {"email": "jane.doe@example.com"})
    assert run["runId"] == "r"
    assert len(rec.requests) == 2
    assert rec.body(0)["idempotencyKey"] == rec.body(1)["idempotencyKey"]
    assert sleeps == [2.0]


def test_retry_after_is_capped_at_30_seconds():
    sleeps: list = []
    client, _ = make(err(503, "catalog_loading", body={"retryAfterSeconds": 600}), httpx.Response(200, json={}), sleeps=sleeps)
    client.catalog_overview()
    assert sleeps == [30.0]


def test_retries_stop_after_max_retries():
    sleeps: list = []
    client, rec = make(err(503, "storage_busy"), sleeps=sleeps)
    with pytest.raises(LoootError) as info:
        client.balance()
    assert info.value.code == "storage_busy"
    assert len(rec.requests) == 3  # 1 try + 2 retries
    assert len(sleeps) == 2
    assert 0.5 <= sleeps[0] < 0.6 and 1.0 <= sleeps[1] < 1.1


def test_500_is_retried_once_only():
    client, rec = make(err(500, "internal_error"), max_retries=5)
    with pytest.raises(LoootError):
        client.balance()
    assert len(rec.requests) == 2


@pytest.mark.parametrize("status,code", [(400, "validation_error"), (402, "insufficient_balance"), (409, "idempotency_conflict"), (503, "billing_unavailable")])
def test_non_retryable_errors_are_never_retried(status, code):
    client, rec = make(err(status, code))
    with pytest.raises(LoootError):
        client.run("x", {})
    assert len(rec.requests) == 1


def test_4xx_is_not_retried_even_if_body_says_retryable():
    client, rec = make(err(400, "validation_error", body={"error": {"code": "validation_error", "message": "m", "retryable": True}}))
    with pytest.raises(LoootError):
        client.balance()
    assert len(rec.requests) == 1


def test_max_retries_zero_turns_retries_off():
    client, rec = make(err(429, "rate_limit_exceeded"), max_retries=0)
    with pytest.raises(LoootError):
        client.balance()
    assert len(rec.requests) == 1


def raise_exc(exc):
    def handler(request):
        raise exc

    return handler


def test_network_error_becomes_looot_error_and_is_retried():
    client, rec = make(
        raise_exc(httpx.ConnectError("dns failed")),
        httpx.Response(200, json={"available": 5}),
    )
    assert client.balance() == {"available": 5}
    assert len(rec.requests) == 2


def test_network_error_after_retries_is_looot_error_status_0():
    client, _ = make(raise_exc(httpx.ConnectError("dns failed")), max_retries=1)
    with pytest.raises(LoootError) as info:
        client.balance()
    e = info.value
    assert (e.status, e.code, e.retryable) == (0, "network_error", True)
    assert isinstance(e.__cause__, httpx.ConnectError)


def test_timeout_becomes_looot_error_timeout():
    client, _ = make(raise_exc(httpx.ReadTimeout("slow")), max_retries=0)
    with pytest.raises(LoootError) as info:
        client.run("x", {}, wait=60)
    assert (info.value.status, info.value.code, info.value.retryable) == (0, "timeout", True)
    assert "same idempotency key" in info.value.retry_hint


def test_missing_token_is_not_retried():
    client, rec = make(token=None)
    with pytest.raises(LoootError):
        client.balance()
    assert rec.requests == []


def test_error_str_and_repr():
    e = LoootError(402, "insufficient_balance", "Top up", "req_1")
    assert str(e) == "insufficient_balance: Top up (request req_1)"
    assert "status=402" in repr(e) and "retryable=False" in repr(e)
