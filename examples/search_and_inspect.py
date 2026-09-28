"""Free, needs LOOOT_TOKEN (catalog.read): search a job, then inspect the first runnable endpoint.

Run: LOOOT_TOKEN=... python examples/search_and_inspect.py
"""

import json

from looot import Looot

with Looot() as looot:
    found = looot.search("verify an email", prefer="cheapest", limit=5)
    for e in found["endpoints"]:
        print(e["endpointId"], e.get("access"), e.get("estimatedPrice"), e.get("priceBasis"))
    top = next((e for e in found["endpoints"] if e.get("access") == "runs_now"), None)
    if top:
        spec = looot.inspect(top["endpointId"])
        print(spec["endpoint"].get("price"))
        print(json.dumps(spec.get("inputSchema"), indent=2))
