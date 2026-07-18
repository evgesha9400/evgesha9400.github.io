# Library catalogue contract

The portal currently remains a static documentation site. The manifest contract validates durable editorial metadata only; it does not fetch, render, execute, or deploy documentation from a library repository.

## `docs/library.yml` version 1

The versioned JSON Schema is `schemas/library-manifest-1.0.schema.json`. A valid manifest has exactly these fields:

```yaml
schema_version: 1
library_id: ig-trading-lib
title: IG Trading Library
pitch: Typed, safety-first clients for developers integrating with documented IG APIs.
repository: evgesha9400/ig-trading-lib
repository_url: https://github.com/evgesha9400/ig-trading-lib
package:
  name: ig-trading-lib
status: planned
categories:
  - brokerage
  - trading
```

The portal validates all of the following before accepting a manifest:

- `library_id` is an exact key in `catalog/library-repositories.json`.
- `repository` is the exact allowlisted identity mapped from `library_id`.
- `repository_url` must exactly equal `https://github.com/<repository>`.
- `title` and `pitch` are length-bounded plain text without markup or line breaks.
- `package.name` is a length-bounded package name, so the portal can derive `pip install <name>` without accepting commands.
- `status` is one of `planned`, `published`, or `deprecated`.
- `categories` contains one to eight unique non-empty plain-text strings.
- unknown keys are rejected.
- URLs other than the exact canonical `repository_url`, paths, commands, plugins, and source-root selection are not contract fields.

## Release event selection

Release identity is a separate, transient event selection. `validate_release_selection` validates an allowlisted repository, a canonical `v`-prefixed semantic-version tag, its matching version, and a lowercase 40-character commit SHA. These values are workflow inputs, not `docs/library.yml` fields, so editorial metadata never becomes self-referential to a future release tag or commit.

## Manual rebuild scaffold

Run **Rebuild allowlisted library documentation** from the `main` branch and supply its four typed release-event inputs: repository, tag, version, and commit. It validates the event before building the portal and uploading an official GitHub Pages artifact. The deploy job is guarded to `refs/heads/main` and uses the fixed `github-pages` environment.

## Future dispatch credential

When upstream-triggered rebuilds are introduced, configure the fine-grained PAT as the Actions secret `LIBRARY_PORTAL_DISPATCH_TOKEN` in each participating library repository. Its repository access must be limited to `evgesha9400/evgesha9400.github.io`, and its minimum repository permission is `Actions: write`.

No token is stored in this portal, and this phase does not make any live dispatches.
