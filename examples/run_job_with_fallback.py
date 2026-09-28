"""PAID: verify one email through the job, cheapest provider first, with fallback.

Needs LOOOT_TOKEN (runs.execute) and a topped-up balance. Costs a few tenths of a cent.
Run: LOOOT_TOKEN=... python examples/run_job_with_fallback.py jane.doe@example.com
"""

import sys

from looot import Looot, LoootError

if len(sys.argv) < 2:
    sys.exit("usage: python examples/run_job_with_fallback.py <email>")

with Looot() as looot:
    try:
        run = looot.run_job(
            "people.email.verify",
            {"email": sys.argv[1]},
            prefer="cheapest",
            fallback={"maxAttempts": 3, "maxCostUsd": 0.05},
            wait=30,
        )
    except LoootError as e:
        if e.code == "insufficient_balance":
            sys.exit(f"Top up first: {e.body.get('topUp', {}).get('checkoutUrl')}")
        raise
    print(run["status"], run.get("outcome"), "served by", (run.get("route") or {}).get("servedBy"))
    print("normalized:", run.get("normalized"))
    print("charged:", run.get("actualCost"))
    if run["status"] == "failed":
        print(run["error"], file=sys.stderr)
