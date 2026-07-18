"""Validate GitHub release metadata and generate portal-owned publication files.

This module deliberately consumes JSON responses gathered from fixed GitHub API
endpoints. It never clones, imports, renders, or executes content from a
library repository.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

from .library_manifest import (
    COMMIT_PATTERN,
    DEFAULT_ALLOWLIST_PATH,
    LibraryManifest,
    LibraryRelease,
    ManifestValidationError,
    load_library_manifest,
    validate_library_manifest,
    validate_release_selection,
)

PORTAL_URL = "https://evgesha9400.github.io"
MANIFEST_PATH = "docs/library.yml"
PUBLICATION_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 32_768


@dataclass(frozen=True)
class PublicationInputs:
    """The four independently validated dispatch selectors."""

    repository: str
    tag: str
    version: str
    commit: str

    def validate(self, *, allowlist_path: Path = DEFAULT_ALLOWLIST_PATH) -> LibraryRelease:
        """Validate the selectors before any network response is inspected."""
        _require_strings(
            repository=self.repository,
            tag=self.tag,
            version=self.version,
            commit=self.commit,
        )
        return validate_release_selection(
            repository=self.repository,
            tag=self.tag,
            version=self.version,
            commit=self.commit,
            allowlist_path=allowlist_path,
        )


@dataclass(frozen=True)
class ReleasePublication:
    """Validated, portal-derived metadata for one immutable library release."""

    manifest: LibraryManifest
    release: LibraryRelease
    published_at: str

    @property
    def source_url(self) -> str:
        """Return the canonical, schema-validated source repository URL."""
        return self.manifest.repository_url

    @property
    def release_url(self) -> str:
        """Return the derived GitHub release URL without trusting an API URL."""
        return f"{self.source_url}/releases/tag/{quote(self.release.tag, safe='.-')}"

    @property
    def documentation_url(self) -> str:
        """Return the derived immutable documentation URL."""
        version = quote(self.release.version, safe=".-")
        return f"{PORTAL_URL}/{self.manifest.library_id}/{version}/"

    @property
    def latest_documentation_url(self) -> str:
        """Return the derived stable documentation alias URL."""
        return f"{PORTAL_URL}/{self.manifest.library_id}/latest/"

    @property
    def install_command(self) -> str:
        """Return the sole package command derived from the validated package name."""
        return f"pip install {self.manifest.package_name}"

    def as_record(self) -> dict[str, object]:
        """Serialize only validated or portal-derived publication provenance."""
        return {
            "schema_version": PUBLICATION_SCHEMA_VERSION,
            "library_id": self.manifest.library_id,
            "title": self.manifest.title,
            "pitch": self.manifest.pitch,
            "repository": self.manifest.repository,
            "package_name": self.manifest.package_name,
            "status": self.manifest.status,
            "categories": list(self.manifest.categories),
            "tag": self.release.tag,
            "version": self.release.version,
            "commit": self.release.commit,
            "published_at": self.published_at,
            "release_url": self.release_url,
            "documentation_url": self.documentation_url,
            "latest_documentation_url": self.latest_documentation_url,
            "source_url": self.source_url,
            "install_command": self.install_command,
        }


def create_release_publication(
    *,
    inputs: PublicationInputs,
    release_response: object,
    tag_reference_response: object,
    annotated_tag_response: object | None,
    manifest_response: object,
    output_directory: Path,
    allowlist_path: Path = DEFAULT_ALLOWLIST_PATH,
) -> ReleasePublication:
    """Validate fixed GitHub API responses and write deterministic portal files.

    Output is created only after every input and response is valid, preventing a
    malformed dispatch from partially updating the catalogue.
    """
    release = inputs.validate(allowlist_path=allowlist_path)
    published_at = _validate_release_response(release_response, release)
    _validate_tag_reference(
        tag_reference_response=tag_reference_response,
        annotated_tag_response=annotated_tag_response,
        release=release,
    )
    manifest = _validate_manifest_response(
        manifest_response,
        expected_repository=release.repository,
        allowlist_path=allowlist_path,
    )
    if manifest.status != "published":
        raise ManifestValidationError("Library manifest status must be published for a release.")

    publication = ReleasePublication(manifest=manifest, release=release, published_at=published_at)
    _write_publication(output_directory, publication)
    return publication


def persist_release_publication(
    publication_directory: Path,
    portal_directory: Path,
    *,
    allowlist_path: Path = DEFAULT_ALLOWLIST_PATH,
) -> tuple[Path, ...]:
    """Verify a generated artifact and persist only its expected portal files."""
    record_path = _find_single_record_path(publication_directory)
    record = _load_json_mapping(record_path)
    publication = _publication_from_record(record, allowlist_path=allowlist_path)
    expected_files = _render_publication_files(publication)
    _reject_stale_publication(publication, portal_directory, allowlist_path=allowlist_path)

    for relative_path, expected_content in expected_files.items():
        source_path = publication_directory / relative_path
        if not source_path.is_file():
            raise ManifestValidationError(f"Publication artifact is missing {relative_path}.")
        if source_path.read_text(encoding="utf-8") != expected_content:
            raise ManifestValidationError(
                f"Publication artifact {relative_path} does not match the fixed portal template."
            )

    changed_paths: list[Path] = []
    for relative_path, content in expected_files.items():
        destination = portal_directory / relative_path
        if destination.is_file() and destination.read_text(encoding="utf-8") == content:
            continue
        _write_text_atomically(destination, content)
        changed_paths.append(relative_path)
    return tuple(changed_paths)


def _reject_stale_publication(
    publication: ReleasePublication,
    portal_directory: Path,
    *,
    allowlist_path: Path,
) -> None:
    """Keep a delayed release event from replacing newer portal provenance."""
    record_path = (
        portal_directory / "catalog" / "releases" / f"{publication.manifest.library_id}.json"
    )
    if not record_path.is_file():
        return

    existing = _publication_from_record(
        _load_json_mapping(record_path), allowlist_path=allowlist_path
    )
    if existing.as_record() == publication.as_record():
        return
    if _parse_timestamp(existing.published_at) >= _parse_timestamp(publication.published_at):
        raise ManifestValidationError(
            "Release publication is stale beside the current portal record."
        )


def _validate_release_response(response: object, release: LibraryRelease) -> str:
    data = _require_mapping(response, "release response")
    if data.get("tag_name") != release.tag:
        raise ManifestValidationError("GitHub release tag_name does not match the requested tag.")
    if data.get("draft") is not False:
        raise ManifestValidationError("GitHub release must be published, non-draft metadata.")
    if not isinstance(data.get("id"), int) or isinstance(data["id"], bool):
        raise ManifestValidationError("GitHub release id must be an integer.")
    published_at = _require_string(data.get("published_at"), "GitHub release published_at")
    _validate_utc_timestamp(published_at)
    return published_at


def _validate_tag_reference(
    *,
    tag_reference_response: object,
    annotated_tag_response: object | None,
    release: LibraryRelease,
) -> None:
    reference = _require_mapping(tag_reference_response, "tag reference response")
    expected_ref = f"refs/tags/{release.tag}"
    if reference.get("ref") != expected_ref:
        raise ManifestValidationError("GitHub tag reference does not match the requested tag.")

    object_data = _require_mapping(reference.get("object"), "GitHub tag reference object")
    object_type = _require_string(object_data.get("type"), "GitHub tag reference object type")
    object_sha = _require_commit_sha(object_data.get("sha"), "GitHub tag reference object SHA")
    if object_type == "commit":
        _validate_resolved_commit(object_sha, release.commit)
        return
    if object_type != "tag":
        raise ManifestValidationError(
            "GitHub tag reference must resolve to a commit or annotated tag."
        )
    if annotated_tag_response is None:
        raise ManifestValidationError(
            "Annotated Git tag response is required for an annotated tag."
        )

    annotated_tag = _require_mapping(annotated_tag_response, "annotated Git tag response")
    if annotated_tag.get("tag") != release.tag:
        raise ManifestValidationError("Annotated Git tag name does not match the requested tag.")
    annotated_object = _require_mapping(annotated_tag.get("object"), "annotated Git tag object")
    if annotated_object.get("type") != "commit":
        raise ManifestValidationError("Annotated Git tag must resolve directly to a commit.")
    resolved_commit = _require_commit_sha(
        annotated_object.get("sha"), "annotated Git tag commit SHA"
    )
    _validate_resolved_commit(resolved_commit, release.commit)


def _validate_resolved_commit(resolved_commit: str, requested_commit: str) -> None:
    if resolved_commit != requested_commit:
        raise ManifestValidationError(
            "GitHub resolved tag commit does not match the requested commit."
        )


def _validate_manifest_response(
    response: object,
    *,
    expected_repository: str,
    allowlist_path: Path,
) -> LibraryManifest:
    data = _require_mapping(response, "manifest response")
    if data.get("type") != "file" or data.get("path") != MANIFEST_PATH:
        raise ManifestValidationError("GitHub manifest response must be the docs/library.yml file.")
    if data.get("encoding") != "base64":
        raise ManifestValidationError("GitHub manifest response must use base64 encoding.")
    content = _require_string(data.get("content"), "GitHub manifest content")
    decoded_content = _decode_base64_manifest(content)
    expected_size = data.get("size")
    if type(expected_size) is not int or expected_size != len(decoded_content):
        raise ManifestValidationError(
            "GitHub manifest response size does not match decoded content."
        )

    manifest_path = _write_temporary_manifest(decoded_content)
    try:
        manifest = validate_library_manifest(
            load_library_manifest(manifest_path), allowlist_path=allowlist_path
        )
    finally:
        manifest_path.unlink(missing_ok=True)
    if manifest.repository != expected_repository:
        raise ManifestValidationError(
            "Library manifest repository does not match the requested repository."
        )
    return manifest


def _write_temporary_manifest(content: bytes) -> Path:
    """Write trusted-size YAML to a private temporary path for the YAML loader."""
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(prefix="portal-library-manifest-", suffix=".yml", delete=False) as file:
        file.write(content)
        return Path(file.name)


def _decode_base64_manifest(content: str) -> bytes:
    compact_content = "".join(content.split())
    try:
        decoded_content = base64.b64decode(compact_content, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ManifestValidationError("GitHub manifest content is not valid base64.") from error
    if not decoded_content or len(decoded_content) > MAX_MANIFEST_BYTES:
        raise ManifestValidationError("GitHub manifest content has an invalid size.")
    try:
        decoded_content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ManifestValidationError("GitHub manifest content must be UTF-8.") from error
    return decoded_content


def _write_publication(output_directory: Path, publication: ReleasePublication) -> None:
    for relative_path, content in _render_publication_files(publication).items():
        _write_text_atomically(output_directory / relative_path, content)


def _render_publication_files(publication: ReleasePublication) -> dict[Path, str]:
    library_id = publication.manifest.library_id
    return {
        Path("catalog") / "releases" / f"{library_id}.json": _render_record(publication),
        Path("docs") / "includes" / f"{library_id}-card.md": _render_card(publication),
        Path("docs") / "includes" / f"{library_id}-details.md": _render_details(publication),
    }


def _render_record(publication: ReleasePublication) -> str:
    return json.dumps(publication.as_record(), indent=2, sort_keys=False) + "\n"


def _render_card(publication: ReleasePublication) -> str:
    title = escape(publication.manifest.title)
    pitch = escape(publication.manifest.pitch)
    version = escape(publication.release.version)
    package = escape(publication.manifest.package_name)
    return f'''<article class="portal-card" data-library="{publication.manifest.library_id}">
  <div class="portal-card-heading">
    <p class="portal-status">documentation available · v{version}</p>
    <h2>{title}</h2>
    <p class="portal-summary">{pitch}</p>
  </div>
  <ul class="portal-points">
    <li>Immutable release documentation</li>
    <li>Latest stable documentation alias</li>
    <li>Safety-first trading guidance</li>
  </ul>
  <p class="portal-install"><code>pip install {package}</code></p>
  <div class="portal-card-actions" aria-label="{title} links">
    <a href="{publication.documentation_url}">Documentation v{version}</a>
    <a href="{publication.latest_documentation_url}">Latest documentation</a>
    <a href="{publication.source_url}">Source code</a>
    <a href="https://pypi.org/project/{package}/">Package on PyPI</a>
  </div>
</article>
'''


def _render_details(publication: ReleasePublication) -> str:
    title = escape(publication.manifest.title)
    pitch = escape(publication.manifest.pitch)
    version = escape(publication.release.version)
    tag = escape(publication.release.tag)
    package = escape(publication.manifest.package_name)
    commit = escape(publication.release.commit)
    return f"""<p class="library-status">documentation available · v{version}</p>

{pitch}

## Install

```bash
pip install {package}
```

## Documentation

- [Version {version} (immutable)]({publication.documentation_url})
- [Latest stable documentation]({publication.latest_documentation_url})
- [Release record]({publication.release_url})
- [Source code]({publication.source_url})

## Published provenance

- Release tag: {tag}
- Source commit: [`{commit}`]({publication.source_url}/commit/{commit})
- Library: {title}

## Safety boundary

Review the versioned documentation and repository safety guidance before connecting credentials
or submitting orders.
"""


def _publication_from_record(
    record: Mapping[str, object],
    *,
    allowlist_path: Path,
) -> ReleasePublication:
    required_keys = {
        "schema_version",
        "library_id",
        "title",
        "pitch",
        "repository",
        "package_name",
        "status",
        "categories",
        "tag",
        "version",
        "commit",
        "published_at",
        "release_url",
        "documentation_url",
        "latest_documentation_url",
        "source_url",
        "install_command",
    }
    if set(record) != required_keys:
        raise ManifestValidationError("Publication record fields do not match the portal schema.")
    if record.get("schema_version") != PUBLICATION_SCHEMA_VERSION:
        raise ManifestValidationError("Publication record has an unsupported schema version.")

    categories = record["categories"]
    if not isinstance(categories, list) or not all(
        isinstance(category, str) for category in categories
    ):
        raise ManifestValidationError("Publication record categories must be a list of strings.")
    manifest_data = {
        "schema_version": 1,
        "library_id": _require_string(record["library_id"], "publication record library_id"),
        "title": _require_string(record["title"], "publication record title"),
        "pitch": _require_string(record["pitch"], "publication record pitch"),
        "repository": _require_string(record["repository"], "publication record repository"),
        "repository_url": _require_string(record["source_url"], "publication record source_url"),
        "package": {"name": _require_string(record["package_name"], "publication record package")},
        "status": _require_string(record["status"], "publication record status"),
        "categories": categories,
    }
    manifest = validate_library_manifest(manifest_data, allowlist_path=allowlist_path)
    if manifest.status != "published":
        raise ManifestValidationError("Publication record manifest status must be published.")
    release = PublicationInputs(
        repository=manifest.repository,
        tag=_require_string(record["tag"], "publication record tag"),
        version=_require_string(record["version"], "publication record version"),
        commit=_require_string(record["commit"], "publication record commit"),
    ).validate(allowlist_path=allowlist_path)
    published_at = _require_string(record["published_at"], "publication record published_at")
    _validate_utc_timestamp(published_at)
    publication = ReleasePublication(manifest=manifest, release=release, published_at=published_at)
    if publication.as_record() != dict(record):
        raise ManifestValidationError("Publication record contains non-derived values.")
    return publication


def _find_single_record_path(publication_directory: Path) -> Path:
    record_paths = tuple((publication_directory / "catalog" / "releases").glob("*.json"))
    if len(record_paths) != 1:
        raise ManifestValidationError(
            "Publication artifact must contain exactly one release record."
        )
    return record_paths[0]


def _load_json_mapping(path: Path) -> Mapping[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestValidationError(
            f"Unable to read publication record {path}: {error}"
        ) from error
    return _require_mapping(data, "publication record")


def _write_text_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ManifestValidationError(f"{name} must be a string-keyed JSON object.")
    return value


def _require_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ManifestValidationError(f"{name} must be a string.")
    return value


def _require_strings(**values: object) -> None:
    for name, value in values.items():
        _require_string(value, name)


def _require_commit_sha(value: object, name: str) -> str:
    commit = _require_string(value, name)
    if not COMMIT_PATTERN.fullmatch(commit):
        raise ManifestValidationError(f"{name} must be a lowercase 40-character Git SHA.")
    return commit


def _validate_utc_timestamp(value: str) -> None:
    _parse_timestamp(value)


def _parse_timestamp(value: str) -> datetime:
    try:
        normalized_value = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized_value)
    except ValueError as error:
        raise ManifestValidationError(
            "GitHub release published_at must be an ISO 8601 timestamp."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestValidationError("GitHub release published_at must include a UTC offset.")
    return parsed


def parse_arguments() -> argparse.Namespace:
    """Parse only local response files and the four validated selectors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--release-response", type=Path, required=True)
    parser.add_argument("--tag-reference-response", type=Path, required=True)
    parser.add_argument("--annotated-tag-response", type=Path)
    parser.add_argument("--manifest-response", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--portal-directory", type=Path)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST_PATH)
    return parser.parse_args()


def _load_json_file(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestValidationError(
            f"Unable to read GitHub API response {path}: {error}"
        ) from error


def main() -> int:
    """Create a validated release publication from previously fetched JSON responses."""
    arguments = parse_arguments()
    try:
        create_release_publication(
            inputs=PublicationInputs(
                repository=arguments.repository,
                tag=arguments.tag,
                version=arguments.version,
                commit=arguments.commit,
            ),
            release_response=_load_json_file(arguments.release_response),
            tag_reference_response=_load_json_file(arguments.tag_reference_response),
            annotated_tag_response=(
                _load_json_file(arguments.annotated_tag_response)
                if arguments.annotated_tag_response is not None
                else None
            ),
            manifest_response=_load_json_file(arguments.manifest_response),
            output_directory=arguments.output_directory,
            allowlist_path=arguments.allowlist,
        )
        if arguments.portal_directory is not None:
            persist_release_publication(
                arguments.output_directory,
                arguments.portal_directory,
                allowlist_path=arguments.allowlist,
            )
    except ManifestValidationError as error:
        print(f"Library release publication failed: {error}")
        return 1
    print("Library release publication validated and generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
