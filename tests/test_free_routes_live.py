"""Live tests against looot's FREE routes only. No run is ever created here.

Run with: pytest -m live
search runs only when LOOOT_TOKEN is set (free, but it needs catalog.read).
"""

import os

import pytest

from looot import Looot, LoootError

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client():
    with Looot() as c:
        yield c


def test_catalog_overview_totals(client):
    overview = client.catalog_overview()
    assert overview["totals"]["endpoints"] > 0
    assert len(overview["categories"]) > 0


def test_catalog_overview_topic_email(client):
    overview = client.catalog_overview(topic="email")
    ids = [job["id"] for job in overview["jobs"]]
    assert "people.email.verify" in ids


def test_public_catalog_by_capability(client):
    page = client.public_catalog(capability="people_email_verify", limit=5)
    assert page["items"]
    for item in page["items"]:
        assert any(p["name"] == "email" and p["required"] for p in item["parameters"])


def test_public_catalog_item(client):
    assert client.public_catalog_item("icypeas-email-verify")["catalogItemId"] == "icypeas-email-verify"


def test_token_route_without_token_is_refused():
    with Looot(token="") as anon:
        with pytest.raises(LoootError):
            anon.search("verify an email")


@pytest.mark.skipif(not os.environ.get("LOOOT_TOKEN"), reason="LOOOT_TOKEN not set")
def test_search(client):
    assert isinstance(client.search("verify an email", limit=3)["endpoints"], list)
