"""PAID: find a work email through the job, with fallback, after checking the balance.

Needs LOOOT_TOKEN (runs.execute, usage.read) and a topped-up balance. Costs a few cents at most.
Run: LOOOT_TOKEN=... python examples/run_job_with_fallback.py "Jane Doe" example.com
"""

import sys

from looot import Looot, LoootError

if len(sys.argv) < 3:
    sys.exit('usage: python examples/run_job_with_fallback.py "<full name>" <domain>')

with Looot(agent="looot-python example") as looot:
    balance = looot.balance()
    link = balance.get("topUpLink") or {}
    if balance["available"] <= 0:
        sys.exit(f"Top up first: {link.get('checkoutUrl') or link.get('dashboardUrl')}")
    try:
        run = looot.run_job(
            "people.email.find",
            {"name": sys.argv[1], "domain": sys.argv[2]},
            fallback={"maxAttempts": 3, "maxCostUsd": 0.05},
            wait=30,
        )
    except LoootError as e:
        if e.code == "insufficient_balance" and e.top_up:
            sys.exit(f"Top up first: {e.top_up.url}")
        sys.exit(f"{e} ({e.retry_hint})")
    if run["status"] not in ("completed", "failed", "blocked", "stopped"):
        run = looot.wait_for_run(run["runId"], timeout=120)
    print(run["status"], run.get("outcome"), "served by", (run.get("route") or {}).get("servedBy"))
    print("normalized:", run.get("normalized"))
    print("charged:", run.get("actualCost"))
    if run.get("error"):
        print(run["error"].get("code"), run["error"].get("retryHint"), file=sys.stderr)
