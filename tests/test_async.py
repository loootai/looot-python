"""AsyncLooot: same surface as Looot, tested with respx. No pytest plugin: each test runs asyncio.run."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
from pathlib import Path

import httpx
import pytest
import respx

from looot import AsyncLooot, Looot, LoootError

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://api.looot.ai"


def test_async_client_matches_generator_output():
    spec = importlib.util.spec_from_file_location("gen_async", ROOT / "scripts" / "gen_async.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    expected = gen.convert((ROOT / "src" / "looot" / "_client.py").read_text())
    actual = (ROOT / "src" / "looot" / "_async_client.py").read_text()
    assert actual == expected, "run: python scripts/gen_async.py"


def public_methods(cls):
    return {n: m for n, m in inspect.getmembers(cls, inspect.isfunction) if not n.startswith("_")}


def test_async_and_sync_have_the_same_methods_and_parameters():
    sync, aio = public_methods(Looot), public_methods(AsyncLooot)
    assert sorted(sync) == sorted(aio)
    for name in sync:
        assert list(inspect.signature(sync[name]).parameters) == list(inspect.signature(aio[name]).parameters), name
        is_async = inspect.iscoroutinefunction(aio[name]) or inspect.isasyncgenfunction(aio[name])
        assert is_async, name


async def sleep_noop(_seconds):
    return None


def client(token="t", **kwargs):
    return AsyncLooot(token, sleep=sleep_noop, **kwargs)


def test_async_catalog_overview_sends_no_token():
    async def main():
        with respx.mock(base_url=BASE) as mock:
            route = mock.get("/v1/catalog/overview").respond(200, json={"jobs": []})
            async with client("abc") as looot:
                await looot.catalog_overview(topic="email")
            req = route.calls.last.request
            assert req.url.params["topic"] == "email"
            assert "authorization" not in req.headers

    asyncio.run(main())


def test_async_run_job_and_201_failed_run():
    async def main():
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/v1/runs").respond(201, json={"runId": "r", "status": "failed", "error": {"code": "route_no_fit"}})
            async with client() as looot:
                run = await looot.run_job("people.email.find", {"name": "Jane Doe", "domain": "example.com"}, fallback=True, wait=20)
            assert run["status"] == "failed"
            req = route.calls.last.request
            assert req.url.params["wait"] == "20"
            body = json.loads(req.content)
            assert body["endpointId"] == "job:people.email.find"
            assert body["fallback"] is True
            assert body["idempotencyKey"].startswith("sdk-")

    asyncio.run(main())


def test_async_every_core_route():
    async def main():
        with respx.mock(base_url=BASE, assert_all_called=True) as mock:
            mock.get("/v1/public-catalog").respond(200, json={"items": []})
            mock.get("/v1/public-catalog/icypeas-email-verify").respond(200, json={"catalogItemId": "x"})
            mock.post("/v1/public-catalog/compare").respond(200, json={})
            mock.get("/v1/catalog/search").respond(200, json={"endpoints": []})
            mock.get("/v1/discover").respond(200, json={"candidates": []})
            mock.get("/v1/catalog/endpoints").respond(200, json={"endpoints": []})
            mock.get("/v1/operations/icypeas-email-verify").respond(200, json={"endpoint": {}})
            mock.get(url__regex=r"/v1/runs/a%2Fb$").respond(200, json={"runId": "a/b", "status": "completed"})
            mock.get("/v1/runs").respond(200, json={"runs": [], "nextCursor": None})
            mock.post("/v1/runs/run_1/cancel").respond(200, json={"status": "stopped"})
            mock.get("/v1/runs/run_1/attempts").respond(200, json={"attempts": []})
            mock.get("/v1/balance").respond(200, json={"available": 1.5})
            mock.get("/v1/top-ups").respond(200, json={"topUps": []})
            mock.get("/v1/ledger").respond(200, json={"entries": []})
            mock.get("/v1/whoami").respond(200, json={"organization": {}})
            mock.post("/v1/capability-requests").respond(201, json={"status": "open"})
            mock.get("/v1/runs/run_1/media/m1").respond(200, content=b"img", headers={"content-type": "image/png"})
            async with client() as looot:
                await looot.public_catalog(limit=1)
                await looot.public_catalog_item("icypeas-email-verify")
                await looot.compare_public_catalog(["a-one", "b-two"])
                await looot.search("email")
                await looot.discover("email")
                await looot.catalog_endpoints(facets=True)
                await looot.inspect("icypeas-email-verify")
                assert (await looot.get_run("a/b"))["runId"] == "a/b"
                await looot.list_runs()
                assert (await looot.cancel_run("run_1"))["status"] == "stopped"
                await looot.run_attempts("run_1")
                assert (await looot.balance())["available"] == 1.5
                await looot.list_top_ups()
                await looot.ledger()
                await looot.whoami()
                await looot.capability_request("t", "d")
                media = await looot.download_media("/v1/runs/run_1/media/m1")
                assert media.content == b"img"

    asyncio.run(main())


def test_async_missing_token_sends_nothing():
    async def main():
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            route = mock.get("/v1/balance").respond(200, json={})
            async with client(token="") as looot:
                with pytest.raises(LoootError) as info:
                    await looot.balance()
            assert info.value.code == "missing_token"
            assert route.call_count == 0

    asyncio.run(main())


def test_async_retries_503_then_succeeds():
    async def main():
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/v1/runs").mock(
                side_effect=[
                    httpx.Response(503, json={"error": {"code": "storage_busy", "message": "busy"}}),
                    httpx.Response(201, json={"runId": "r", "status": "queued"}),
                ]
            )
            async with client() as looot:
                run = await looot.run("icypeas-email-verify", {"email": "jane.doe@example.com"})
            assert run["runId"] == "r"
            keys = [json.loads(c.request.content)["idempotencyKey"] for c in route.calls]
            assert len(keys) == 2 and keys[0] == keys[1]

    asyncio.run(main())


def test_async_402_and_network_error():
    async def main():
        with respx.mock(base_url=BASE) as mock:
            mock.get("/v1/balance").respond(
                402, json={"error": {"code": "insufficient_balance", "message": "m", "requestId": "req_1"}, "topUp": {"checkoutUrl": "https://checkout.example.com/x"}}
            )
            mock.get("/v1/whoami").mock(side_effect=httpx.ConnectError("down"))
            async with client(max_retries=0) as looot:
                with pytest.raises(LoootError) as info:
                    await looot.balance()
                assert info.value.top_up.url == "https://checkout.example.com/x"
                with pytest.raises(LoootError) as info:
                    await looot.whoami()
                assert (info.value.status, info.value.code) == (0, "network_error")

    asyncio.run(main())


def test_async_iter_runs_and_wait_for_run():
    async def main():
        with respx.mock(base_url=BASE) as mock:
            mock.get("/v1/runs").mock(
                side_effect=[
                    httpx.Response(200, json={"runs": [{"runId": "a"}], "nextCursor": "c"}),
                    httpx.Response(200, json={"runs": [{"runId": "b"}], "nextCursor": None}),
                ]
            )
            mock.get("/v1/runs/r").mock(
                side_effect=[
                    httpx.Response(200, json={"status": "running"}),
                    httpx.Response(200, json={"status": "completed"}),
                ]
            )
            async with client() as looot:
                ids = [r["runId"] async for r in looot.iter_runs()]
                run = await looot.wait_for_run("r")
            assert ids == ["a", "b"]
            assert run["status"] == "completed"

    asyncio.run(main())
