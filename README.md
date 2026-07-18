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
