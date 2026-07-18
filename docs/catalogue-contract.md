# Library catalogue contract

The portal is a static documentation site. The manifest contract validates durable editorial metadata only; it never fetches, renders, executes, imports, or deploys a library repository's code or documentation.

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

## Release publication ingress

The only upstream event ingress is **Rebuild allowlisted library documentation** on the portal's `main` branch. It accepts four untrusted selectors: repository, tag, version, and commit.

- It rejects a selector before contacting GitHub unless the repository is allowlisted and the tag, version, and SHA are canonical.
- It queries only fixed GitHub API paths for the allowlisted repository: release by tag, tag reference, annotated tag when necessary, and `docs/library.yml` at that tag.
- The release must be published and non-draft, and its tag must resolve to the supplied commit.
- The tagged manifest must pass this schema, match the requested repository, and declare `status: published`.
- The portal derives all source, release, package, immutable-documentation, and `latest` URLs itself.
- The portal HTML-escapes manifest text and writes only a derived release record plus fixed-template card and detail snippets.
- A delayed event cannot replace a portal record published at the same or a later time.
- The portal does not clone, render, execute, import, or deploy upstream code or documentation.

The ingestion job can write only portal-owned release metadata. A separate build job reads the persisted portal commit, and the deployment job alone receives `pages: write` and `id-token: write` for the fixed `github-pages` environment.

## Future dispatch credential

Configure the fine-grained PAT as the Actions secret `LIBRARY_PORTAL_DISPATCH_TOKEN` in each participating library repository. Its repository access must be limited to `evgesha9400/evgesha9400.github.io`, and its minimum repository permission is `Actions: write`. The caller dispatches this fixed portal workflow on `main`; it cannot supply a destination, URL, path, workflow, or configuration.

No upstream token is stored in this portal.
