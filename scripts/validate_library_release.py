"""Validate durable library metadata or an offline release selection."""

from __future__ import annotations

import argparse
from pathlib import Path

from .library_manifest import (
    DEFAULT_ALLOWLIST_PATH,
    LibraryManifest,
    LibraryRelease,
    ManifestValidationError,
    load_library_manifest,
    validate_library_manifest,
    validate_release_selection,
)


def parse_arguments() -> argparse.Namespace:
    """Parse either a local manifest path or the four workflow dispatch inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST_PATH)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--tag")
    parser.add_argument("--version")
    parser.add_argument("--commit")
    return parser.parse_args()


def validate_requested_release(arguments: argparse.Namespace) -> LibraryManifest | LibraryRelease:
    """Validate one durable manifest or one explicit, transient release selection."""
    if arguments.manifest is not None:
        _validate_manifest_argument_set(arguments)
        return validate_library_manifest(
            load_library_manifest(arguments.manifest), allowlist_path=arguments.allowlist
        )

    _validate_release_argument_set(arguments)
    return validate_release_selection(
        repository=arguments.repository,
        tag=arguments.tag,
        version=arguments.version,
        commit=arguments.commit,
        allowlist_path=arguments.allowlist,
    )


def _validate_manifest_argument_set(arguments: argparse.Namespace) -> None:
    if any((arguments.repository, arguments.tag, arguments.version, arguments.commit)):
        raise ManifestValidationError("--manifest cannot be combined with explicit release inputs.")


def _validate_release_argument_set(arguments: argparse.Namespace) -> None:
    missing = [
        name
        for name in ("repository", "tag", "version", "commit")
        if getattr(arguments, name) is None
    ]
    if missing:
        raise ManifestValidationError(f"Missing required release inputs: {', '.join(missing)}.")


def main() -> int:
    """Report a concise manifest or release validation result for local and Actions use."""
    arguments = parse_arguments()
    try:
        validate_requested_release(arguments)
    except ManifestValidationError as error:
        print(f"Library contract validation failed: {error}")
        return 1

    target = "manifest" if arguments.manifest is not None else "release"
    print(f"Library {target} validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
