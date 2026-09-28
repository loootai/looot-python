---
name: looot-python
description: Work on looot-python, the httpx client for the public looot REST API. Use when adding or changing a method, a test or an example, or when preparing a PyPI release.
---

# looot-python

## What this repo is

A single-dependency Python client (`httpx==0.28.1`) for `https://api.looot.ai`. Methods map
one to one to REST routes and return plain dicts. Same surface as looot-js; keep them aligned.

## Build and test

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pytest              # offline, httpx.MockTransport
.venv/bin/pytest -m live      # free public routes only; search only if LOOOT_TOKEN is set
bash scripts/leak-scan.sh .
git config core.hooksPath .githooks
```

## Dependencies

Exact pins only. `pin-guard/verify.py` covers npm only, so for a Python package check the
release on `https://pypi.org/pypi/<name>/<version>/json`: skip a version younger than 7 days,
a yanked one, or one from a new maintainer. Regenerate `requirements-dev.lock` with
`pip freeze` after any change.

## Release later (only after the owner says yes)

1. Remove the `Private :: Do Not Upload` classifier from `pyproject.toml`.
2. Bump `pyproject.toml`, `src/looot/__init__.py` and `CHANGELOG.md`.
3. Build with the pinned hatchling, upload with a scoped PyPI token, tag `vX.Y.Z`.

## Public looot surface this repo may use

`https://api.looot.ai/openapi.json`, `/llms.txt`, `/llms-full.txt`, `/catalog/*.md`, the REST
routes under `https://api.looot.ai/v1/`, and `https://looot.ai/docs`.

## Never

- Copy code or text from the private gateway repo.
- Commit a token, key, `.env` file or any secret.
- Write internal hosts, local machine paths, workspace or customer ids, or personal emails.
- Name private repos or private branches.
- Call a paid route from a test.
