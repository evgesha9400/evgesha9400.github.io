# evgesha9400.github.io

Developer-first documentation hub for Evgeny Aleshin's maintained public libraries.

## Local development

```bash
uv sync
uv run playwright install chromium
uv run mkdocs serve
```

Open the local address printed by MkDocs to view the portal.

## Verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run mkdocs build --strict
uv run python scripts/check_links.py --site site
uv run pytest
```

The browser suite produces an inspectable mobile screenshot in `test-results/`.
GitHub Actions runs the same local checks, validates external links, and deploys the built site to GitHub Pages only from `main`.

## Library catalogue contract

`schemas/library-manifest-1.0.schema.json` defines the versioned contract for a participating library's `docs/library.yml`. It requires durable developer-facing metadata and package metadata without accepting executable commands. Release identity is a separate validated rebuild event. `catalog/library-repositories.json` is the deliberately minimal allowlist: only IG Trading Library and KuCoin Futures Library identities are accepted.

The manually runnable **Rebuild allowlisted library documentation** workflow validates its repository, tag, version, and commit inputs before rebuilding the current static portal. It does not fetch, render, or execute upstream content in this phase. Deployment is allowed only when the workflow runs from `main`.

Future upstream-triggered rebuilds require a fine-grained PAT stored in each participating library repository as the Actions secret `LIBRARY_PORTAL_DISPATCH_TOKEN`. Scope the token to the `evgesha9400/evgesha9400.github.io` repository only, with the minimum `Actions: write` permission. Do not commit the token or add it as a portal repository secret.
