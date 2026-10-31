"""Free, needs LOOOT_TOKEN (catalog.read): three searches at once with AsyncLooot.

Run: LOOOT_TOKEN=... python examples/async_search.py
"""

import asyncio

from looot import AsyncLooot


async def main() -> None:
    async with AsyncLooot() as looot:
        asks = ["find a work email", "verify an email", "company from a domain"]
        pages = await asyncio.gather(*(looot.search(q, prefer="cheapest", limit=3) for q in asks))
        for ask, page in zip(asks, pages):
            print(ask, "->", [row["endpointId"] for row in page["endpoints"]])


asyncio.run(main())
