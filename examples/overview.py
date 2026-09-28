"""Free, no token: what the catalog covers, then the jobs that match "email".

Run: python examples/overview.py
"""

from looot import Looot

with Looot() as looot:
    totals = looot.catalog_overview()["totals"]
    print(f"{totals['endpoints']} endpoints, {totals['jobs']} jobs, {totals['providers']} providers")
    for job in looot.catalog_overview(topic="email")["jobs"]:
        print(f"{job['id']:<32} {job['providerCount']} providers, from ${job['cheapestPerCall']} per call")
