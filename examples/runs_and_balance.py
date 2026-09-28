"""Free, needs LOOOT_TOKEN (runs.read, usage.read): balance, recent runs, one run's receipts.

Run: LOOOT_TOKEN=... python examples/runs_and_balance.py
"""

import json

from looot import Looot

with Looot() as looot:
    b = looot.balance()
    print(f"available ${b['available']}, reserved ${b['reserved']}, minimum top-up ${b.get('topUpLink', {}).get('minimumUsd')}")
    runs = looot.list_runs(limit=5).get("runs") or []
    for r in runs:
        print(r["runId"], r["status"], r.get("endpointId"), r.get("actualCost"))
    if runs:
        for attempt in looot.run_attempts(runs[0]["runId"])["attempts"]:
            print(json.dumps(attempt))
