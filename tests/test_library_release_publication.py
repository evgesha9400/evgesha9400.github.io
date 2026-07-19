from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest
import yaml

from scripts.library_manifest import ManifestValidationError
from scripts.library_release_publication import (
    PublicationInputs,
    create_release_publication,
    persist_release_publication,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = PROJECT_ROOT / "catalog" / "library-repositories.json"
REBUILD_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "rebuild-library-pages.yml"
HOME_PAGE_PATH = PROJECT_ROOT / "docs" / "index.md"
IG_LIBRARY_PAGE_PATH = PROJECT_ROOT / "docs" / "libraries" / "ig-trading-lib.md"

REPOSITORY = "evgesha9400/ig-trading-lib"
TAG = "v3.0.0"
VERSION = "3.0.0"
COMMIT = "a" * 40


def published_manifest(*, status: str = "published") -> str:
    return "\n".join(
        (
            "schema_version: 1",
            "library_id: ig-trading-lib",
            "title: IG Trading Library",
            "pitch: Safe, typed synchronous and asynchronous IG REST and streaming clients.",
            "repository: evgesha9400/ig-trading-lib",
            "repository_url: https://github.com/evgesha9400/ig-trading-lib",
            "package:",
            "  name: ig-trading-lib",
            f"status: {status}",
            "categories:",
            "  - brokerage",
            "  - trading",
            "",
        )
    )


def inputs(
    *,
    repository: str = REPOSITORY,
    tag: str = TAG,
    version: str = VERSION,
    commit: str = COMMIT,
) -> PublicationInputs:
    return PublicationInputs(repository=repository, tag=tag, version=version, commit=commit)


def release_response(*, draft: bool = False, tag: str = TAG) -> dict[str, object]:
    return {
        "id": 3,
        "tag_name": tag,
        "draft": draft,
        "published_at": "2026-07-18T12:00:00Z",
    }


def tag_reference_response(*, sha: str = COMMIT, object_type: str = "commit") -> dict[str, object]:
    return {
        "ref": f"refs/tags/{TAG}",
        "object": {"type": object_type, "sha": sha},
    }


def manifest_response(manifest: str) -> dict[str, object]:
    encoded_manifest = base64.b64encode(manifest.encode("utf-8")).decode("ascii")
    return {
        "type": "file",
        "path": "docs/library.yml",
        "encoding": "base64",
        "size": len(manifest.encode("utf-8")),
        "content": encoded_manifest,
    }


def create_publication(tmp_path: Path, **overrides: object) -> Path:
    output_directory = tmp_path / "publication"
    create_release_publication(
        inputs=overrides.get("inputs", inputs()),
        release_response=overrides.get("release_response", release_response()),
        tag_reference_response=overrides.get("tag_reference_response", tag_reference_response()),
        annotated_tag_response=overrides.get("annotated_tag_response"),
        manifest_response=overrides.get(
            "manifest_response", manifest_response(published_manifest())
        ),
        output_directory=output_directory,
        allowlist_path=ALLOWLIST_PATH,
    )
    return output_directory


def test_published_release_generates_only_derived_portal_files(tmp_path: Path) -> None:
    output_directory = create_publication(tmp_path)

    record_path = output_directory / "catalog/releases/ig-trading-lib.json"
    card_path = output_directory / "docs/includes/ig-trading-lib-card.md"
    details_path = output_directory / "docs/includes/ig-trading-lib-details.md"
    record = json.loads(record_path.read_text(encoding="utf-8"))

    assert record == {
        "schema_version": 1,
        "library_id": "ig-trading-lib",
        "title": "IG Trading Library",
        "pitch": "Safe, typed synchronous and asynchronous IG REST and streaming clients.",
        "repository": REPOSITORY,
        "package_name": "ig-trading-lib",
        "status": "published",
        "categories": ["brokerage", "trading"],
        "tag": TAG,
        "version": VERSION,
        "commit": COMMIT,
        "published_at": "2026-07-18T12:00:00Z",
        "release_url": "https://github.com/evgesha9400/ig-trading-lib/releases/tag/v3.0.0",
        "documentation_url": "https://evgesha9400.github.io/ig-trading-lib/3.0.0/",
        "latest_documentation_url": "https://evgesha9400.github.io/ig-trading-lib/latest/",
        "source_url": "https://github.com/evgesha9400/ig-trading-lib",
        "install_command": "pip install ig-trading-lib",
    }
    card = card_path.read_text(encoding="utf-8")
    details = details_path.read_text(encoding="utf-8")

    assert 'data-library="ig-trading-lib"' in card
    assert "documentation available · v3.0.0" in card
    assert "pip install ig-trading-lib" in card
    assert "https://evgesha9400.github.io/ig-trading-lib/3.0.0/" in card
    assert "https://evgesha9400.github.io/ig-trading-lib/latest/" in card
    assert "Safe, typed synchronous and asynchronous IG REST and streaming clients." in card
    assert "Version 3.0.0 (immutable)" in details
    assert "Release tag: v3.0.0" in details


def test_publication_is_deterministic(tmp_path: Path) -> None:
    first = create_publication(tmp_path / "first")
    second = create_publication(tmp_path / "second")

    for relative_path in (
        "catalog/releases/ig-trading-lib.json",
        "docs/includes/ig-trading-lib-card.md",
        "docs/includes/ig-trading-lib-details.md",
    ):
        assert (first / relative_path).read_bytes() == (second / relative_path).read_bytes()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"inputs": inputs(repository="evgesha9400/not-allowed")}, "allowlisted"),
        ({"inputs": inputs(commit="b" * 40)}, "resolved tag commit"),
        ({"release_response": release_response(draft=True)}, "published, non-draft"),
        ({"release_response": release_response(tag="v3.0.1")}, "release tag_name"),
        (
            {"manifest_response": manifest_response(published_manifest(status="planned"))},
            "published",
        ),
        (
            {
                "manifest_response": {
                    "type": "file",
                    "path": "docs/library.yml",
                    "encoding": "utf-8",
                    "content": "bad",
                }
            },
            "base64",
        ),
    ],
)
def test_malicious_or_stale_release_inputs_are_rejected_before_output(
    tmp_path: Path,
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ManifestValidationError, match=message):
        create_publication(tmp_path, **overrides)

    assert not (tmp_path / "publication").exists()


def test_annotated_tag_must_resolve_to_the_exact_requested_commit(tmp_path: Path) -> None:
    with pytest.raises(ManifestValidationError, match="resolved tag commit"):
        create_publication(
            tmp_path,
            tag_reference_response=tag_reference_response(object_type="tag", sha="b" * 40),
            annotated_tag_response={
                "tag": TAG,
                "object": {"type": "commit", "sha": "c" * 40},
            },
        )


def test_persist_recreates_only_the_expected_portal_files(tmp_path: Path) -> None:
    publication_directory = create_publication(tmp_path)
    portal_directory = tmp_path / "portal"
    portal_directory.mkdir()

    changed_paths = persist_release_publication(publication_directory, portal_directory)

    assert changed_paths == (
        Path("catalog/releases/ig-trading-lib.json"),
        Path("docs/includes/ig-trading-lib-card.md"),
        Path("docs/includes/ig-trading-lib-details.md"),
    )
    assert (portal_directory / changed_paths[0]).is_file()
    assert (portal_directory / changed_paths[1]).is_file()
    assert (portal_directory / changed_paths[2]).is_file()


def test_persist_rejects_tampered_generated_content(tmp_path: Path) -> None:
    publication_directory = create_publication(tmp_path)
    card_path = publication_directory / "docs/includes/ig-trading-lib-card.md"
    card_path.write_text("unexpected template", encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="does not match"):
        persist_release_publication(publication_directory, tmp_path / "portal")


def test_persist_rejects_a_delayed_release_event(tmp_path: Path) -> None:
    current_publication = create_publication(tmp_path / "current")
    portal_directory = tmp_path / "portal"
    persist_release_publication(current_publication, portal_directory)

    delayed_publication = tmp_path / "delayed"
    create_release_publication(
        inputs=inputs(tag="v3.0.1", version="3.0.1", commit="b" * 40),
        release_response={**release_response(tag="v3.0.1"), "published_at": "2026-07-17T12:00:00Z"},
        tag_reference_response={
            "ref": "refs/tags/v3.0.1",
            "object": {"type": "commit", "sha": "b" * 40},
        },
        annotated_tag_response=None,
        manifest_response=manifest_response(published_manifest()),
        output_directory=delayed_publication,
        allowlist_path=ALLOWLIST_PATH,
    )

    with pytest.raises(ManifestValidationError, match="stale"):
        persist_release_publication(delayed_publication, portal_directory)

    current_record = json.loads(
        (portal_directory / "catalog/releases/ig-trading-lib.json").read_text(encoding="utf-8")
    )
    assert current_record["version"] == VERSION


def test_rebuild_workflow_is_workflow_dispatch_only_and_uses_fixed_api_paths() -> None:
    workflow = REBUILD_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "repository_dispatch:" not in workflow
    assert "github.event.client_payload" not in workflow
    assert "releases/tags/$LIBRARY_TAG" in workflow
    assert "git/ref/tags/$LIBRARY_TAG" in workflow
    assert '"repos/$LIBRARY_REPOSITORY/contents/docs/library.yml"' in workflow
    assert '-f "ref=$LIBRARY_TAG"' in workflow
    assert "gh api" in workflow
    assert "git clone" not in workflow
    assert "contents: write" in workflow
    assert '"$GITHUB_REF" != "refs/heads/main"' in workflow
    assert "actions/deploy-pages@v4" in workflow


def test_rebuild_workflow_embedded_python_sources_compile_without_indentation() -> None:
    """The annotated-tag API branch must not pass YAML indentation to Python."""
    workflow = yaml.safe_load(REBUILD_WORKFLOW_PATH.read_text(encoding="utf-8"))
    fetch_metadata_step = next(
        step
        for step in workflow["jobs"]["ingest"]["steps"]
        if step.get("name") == "Fetch fixed public release metadata"
    )
    embedded_sources = re.findall(
        r"uv run python -c '(.*?)' \"\$API_DIRECTORY/tag-reference\.json\"",
        fetch_metadata_step["run"],
        flags=re.DOTALL,
    )

    assert len(embedded_sources) == 2
    for source in embedded_sources:
        compile(source, str(REBUILD_WORKFLOW_PATH), "exec")


def test_ig_pages_include_only_portal_owned_release_snippets() -> None:
    home_page = HOME_PAGE_PATH.read_text(encoding="utf-8")
    library_page = IG_LIBRARY_PAGE_PATH.read_text(encoding="utf-8")

    assert '--8<-- "docs/includes/ig-trading-lib-card.md"' in home_page
    assert '--8<-- "docs/includes/ig-trading-lib-details.md"' in library_page
    assert "docs/includes/ig-trading-card.md" not in home_page
    assert "docs/includes/ig-trading-details.md" not in library_page
