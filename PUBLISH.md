# Publishing looot to PyPI

The release workflow (`.github/workflows/release.yml`) builds and uploads the package when a
tag like `v0.2.0` is pushed. It uses PyPI trusted publishing, so no API token is stored in
GitHub or anywhere else. Nothing has been uploaded yet.

## Package name

- PyPI project name: `looot`. On 2026-10-31 https://pypi.org/project/looot/ answered 404, so
  the name is free. The first upload claims it.
- If PyPI refuses the name at upload (it blocks some names that look like existing ones), use
  `looot-sdk`. Change `name` in `pyproject.toml` and the `url` in `release.yml`, then redo
  step 2 with that name. The import stays `import looot`.

## One-time setup (Walid)

1. Sign in to https://pypi.org (or create the account) with two-factor auth on.
2. Add a pending trusted publisher at https://pypi.org/manage/account/publishing/ under
   "Add a new pending publisher", tab GitHub, with exactly these values:

   | Field | Value |
   | --- | --- |
   | PyPI Project Name | `looot` |
   | Owner | `loootai` |
   | Repository name | `looot-python` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. In GitHub, create the environment: https://github.com/loootai/looot-python/settings/environments,
   "New environment", name `pypi`. Optional: add yourself under "Required reviewers" so every
   upload waits for your click, and limit "Deployment branches and tags" to tags `v*`.

## Each release

1. Bump `__version__` in `src/looot/_version.py` and add a section to `CHANGELOG.md`.
2. Run the checks locally:

   ```bash
   .venv/bin/pytest && .venv/bin/python scripts/gen_async.py --check && bash scripts/leak-scan.sh .
   ```

3. Commit to `main`, then tag and push the tag. For 0.2.0:

   ```bash
   git tag -a v0.2.0 -m "looot 0.2.0" && git push origin v0.2.0
   ```

The workflow runs the tests, checks that the tag equals the package version, builds the sdist
and wheel, and uploads them. Watch it at https://github.com/loootai/looot-python/actions. When
it is green, https://pypi.org/project/looot/ shows the release and `pip install looot` works.

A PyPI version can never be uploaded twice. If an upload goes wrong, fix it, bump to the next
patch version and tag again. Yank a bad release from the PyPI project page, do not delete it.
