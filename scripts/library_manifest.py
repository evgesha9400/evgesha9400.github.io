"""Validate the offline contract for allowlisted library documentation metadata."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from yaml.constructor import ConstructorError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALLOWLIST_PATH = PROJECT_ROOT / "catalog" / "library-repositories.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "library-manifest-1.0.schema.json"
TAG_PATTERN = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class ManifestValidationError(ValueError):
    """Raised when portal library metadata or release selection is invalid."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that makes duplicate mapping keys invalid."""


def _construct_mapping_without_duplicate_keys(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "manifest keys must be strings",
                key_node.start_mark,
            )
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicate_keys,
)


@dataclass(frozen=True)
class LibraryRelease:
    """A validated, immutable release selection."""

    repository: str
    tag: str
    version: str
    commit: str


@dataclass(frozen=True)
class LibraryManifest:
    """Validated durable editorial metadata from docs/library.yml."""

    library_id: str
    title: str
    pitch: str
    repository: str
    repository_url: str
    package_name: str
    status: str
    categories: tuple[str, ...]


def load_library_manifest(path: Path) -> dict[str, Any]:
    """Read a YAML manifest while refusing syntax errors and duplicate keys."""
    try:
        content = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    except (OSError, yaml.YAMLError) as error:
        raise ManifestValidationError(f"Unable to read manifest {path}: {error}") from error

    if not isinstance(content, dict):
        raise ManifestValidationError("Manifest root must be a mapping.")
    return content


def validate_library_manifest(
    manifest_data: Mapping[str, Any],
    *,
    allowlist_path: Path = DEFAULT_ALLOWLIST_PATH,
) -> LibraryManifest:
    """Validate a complete docs/library.yml manifest against schema and portal policy."""
    _validate_manifest_schema(manifest_data)
    _validate_repository(manifest_data["repository"], allowlist_path)
    _validate_library_identity(
        library_id=manifest_data["library_id"],
        repository=manifest_data["repository"],
        allowlist_path=allowlist_path,
    )
    _validate_repository_url(
        repository=manifest_data["repository"],
        repository_url=manifest_data["repository_url"],
    )
    return LibraryManifest(
        library_id=manifest_data["library_id"],
        title=manifest_data["title"],
        pitch=manifest_data["pitch"],
        repository=manifest_data["repository"],
        repository_url=manifest_data["repository_url"],
        package_name=manifest_data["package"]["name"],
        status=manifest_data["status"],
        categories=tuple(manifest_data["categories"]),
    )


def validate_release_selection(
    *,
    repository: str,
    tag: str,
    version: str,
    commit: str,
    allowlist_path: Path = DEFAULT_ALLOWLIST_PATH,
) -> LibraryRelease:
    """Validate workflow dispatch inputs before any portal build or deployment."""
    _validate_repository(repository, allowlist_path)
    _validate_tag_and_version(tag, version)
    _validate_commit(commit)
    return LibraryRelease(repository=repository, tag=tag, version=version, commit=commit)


def _validate_manifest_schema(manifest_data: Mapping[str, Any]) -> None:
    schema_version = manifest_data.get("schema_version")
    if type(schema_version) is not int:
        raise ManifestValidationError("schema_version must be the integer 1.")

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(dict(manifest_data)), key=lambda error: list(error.path))
    if not errors:
        return

    error = errors[0]
    location = ".".join(str(part) for part in error.absolute_path) or "manifest"
    raise ManifestValidationError(f"{location}: {error.message}")


def _validate_repository(repository: str, allowlist_path: Path) -> None:
    allowed_repositories = set(_load_allowlisted_libraries(allowlist_path).values())
    if repository not in allowed_repositories:
        raise ManifestValidationError(f"repository is not allowlisted: {repository!r}")


def _validate_library_identity(
    *,
    library_id: str,
    repository: str,
    allowlist_path: Path,
) -> None:
    allowed_libraries = _load_allowlisted_libraries(allowlist_path)
    expected_repository = allowed_libraries.get(library_id)
    if expected_repository is None:
        raise ManifestValidationError(f"library_id is not allowlisted: {library_id!r}")
    if repository != expected_repository:
        raise ManifestValidationError(
            f"library_id {library_id!r} must map to repository {expected_repository!r}."
        )


def _validate_repository_url(*, repository: str, repository_url: str) -> None:
    expected_repository_url = f"https://github.com/{repository}"
    if repository_url != expected_repository_url:
        raise ManifestValidationError(f"repository_url must equal {expected_repository_url!r}.")


def _load_allowlisted_libraries(path: Path) -> dict[str, str]:
    try:
        allowlist = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestValidationError(
            f"Unable to read repository allowlist {path}: {error}"
        ) from error

    libraries = allowlist.get("libraries") if isinstance(allowlist, dict) else None
    if not isinstance(libraries, dict) or not all(
        isinstance(library_id, str) and isinstance(repository, str)
        for library_id, repository in libraries.items()
    ):
        raise ManifestValidationError(
            "Repository allowlist must contain a string-to-string libraries mapping."
        )
    return libraries


def _validate_tag_and_version(tag: str, version: str) -> None:
    if not TAG_PATTERN.fullmatch(tag) or not _is_canonical_semver(tag.removeprefix("v")):
        raise ManifestValidationError(
            f"tag is not a canonical v-prefixed semantic version: {tag!r}"
        )
    if not VERSION_PATTERN.fullmatch(version) or not _is_canonical_semver(version):
        raise ManifestValidationError(f"version is not a canonical semantic version: {version!r}")
    if tag != f"v{version}":
        raise ManifestValidationError(f"tag {tag!r} must equal v{version!r}.")


def _is_canonical_semver(version: str) -> bool:
    prerelease = version.partition("-")[2].partition("+")[0]
    return not any(
        part.isdigit() and len(part) > 1 and part.startswith("0") for part in prerelease.split(".")
    )


def _validate_commit(commit: str) -> None:
    if not COMMIT_PATTERN.fullmatch(commit):
        raise ManifestValidationError("commit must be a lowercase 40-character Git SHA.")
