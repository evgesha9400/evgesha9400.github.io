from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.library_manifest import (
    ManifestValidationError,
    load_library_manifest,
    validate_library_manifest,
    validate_release_selection,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = PROJECT_ROOT / "catalog" / "library-repositories.json"
REBUILD_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "rebuild-library-pages.yml"
DEPLOY_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "deploy-pages.yml"
CONTRACT_DOCUMENTATION_PATH = PROJECT_ROOT / "docs" / "catalogue-contract.md"


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "library_id": "ig-trading-lib",
        "title": "IG Trading Library",
        "pitch": "Typed, safety-first clients for developers integrating with documented IG APIs.",
        "repository": "evgesha9400/ig-trading-lib",
        "repository_url": "https://github.com/evgesha9400/ig-trading-lib",
        "package": {"name": "ig-trading-lib"},
        "status": "planned",
        "categories": ["brokerage", "trading"],
    }


def test_allowlist_contains_only_the_two_participating_library_identities() -> None:
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))

    assert allowlist == {
        "libraries": {
            "ig-trading-lib": "evgesha9400/ig-trading-lib",
            "kucoin-futures-lib": "evgesha9400/kucoin-futures-lib",
        }
    }


def test_valid_manifest_is_accepted() -> None:
    manifest = validate_library_manifest(valid_manifest(), allowlist_path=ALLOWLIST_PATH)

    assert manifest.repository == "evgesha9400/ig-trading-lib"
    assert manifest.library_id == "ig-trading-lib"
    assert manifest.repository_url == "https://github.com/evgesha9400/ig-trading-lib"
    assert manifest.package_name == "ig-trading-lib"
    assert manifest.categories == ("brokerage", "trading")
    assert not hasattr(manifest, "tag")
    assert not hasattr(manifest, "version")
    assert not hasattr(manifest, "commit")


def test_valid_release_selection_is_accepted() -> None:
    release = validate_release_selection(
        repository="evgesha9400/kucoin-futures-lib",
        tag="v2.0.0-rc.1",
        version="2.0.0-rc.1",
        commit="b" * 40,
        allowlist_path=ALLOWLIST_PATH,
    )

    assert release.repository == "evgesha9400/kucoin-futures-lib"
    assert release.tag == "v2.0.0-rc.1"


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("repository", "evgesha9400/unknown-library", "allowlisted"),
        ("repository", "../../etc/passwd", "repository"),
        ("schema_version", 1.0, "schema_version"),
        ("library_id", "unknown-library", "library_id"),
        ("title", "<script>alert(1)</script>", "title"),
        ("title", "T" * 101, "title"),
        ("pitch", "<p>HTML is not allowed in the developer-first pitch.</p>", "pitch"),
        ("pitch", "P" * 281, "pitch"),
        ("repository_url", "http://github.com/evgesha9400/ig-trading-lib", "repository_url"),
        ("repository_url", "https://github.com/evgesha9400/ig-trading-lib/", "repository_url"),
        ("package", {"name": "ig-trading-lib; curl example.test"}, "package"),
        ("package", {"name": "a" * 101}, "package"),
        ("package", {"name": "ig-trading-lib", "command": "pip install"}, "package"),
        ("status", "unreviewed", "status"),
        ("categories", [], "categories"),
        ("categories", [""], "categories"),
        ("categories", ["  "], "categories"),
        ("documentation_path", "docs/../../private", "Additional properties"),
        ("source_url", "https://169.254.169.254/latest/meta-data", "Additional properties"),
        ("source_url", "https://127.0.0.1:8080/admin", "Additional properties"),
        ("tag", "v1.2.3", "Additional properties"),
        ("version", "1.2.3", "Additional properties"),
        ("commit", "a" * 40, "Additional properties"),
    ],
)
def test_invalid_manifest_data_is_rejected(field: str, value: object, error: str) -> None:
    manifest_data = valid_manifest()
    manifest_data[field] = value

    with pytest.raises(ManifestValidationError, match=error):
        validate_library_manifest(manifest_data, allowlist_path=ALLOWLIST_PATH)


def test_mismatched_semver_tag_and_version_are_rejected() -> None:
    with pytest.raises(ManifestValidationError, match="must equal"):
        validate_release_selection(
            repository="evgesha9400/ig-trading-lib",
            tag="v1.2.4",
            version="1.2.3",
            commit="a" * 40,
            allowlist_path=ALLOWLIST_PATH,
        )


def test_mismatched_library_identity_and_repository_are_rejected() -> None:
    manifest_data = valid_manifest()
    manifest_data["library_id"] = "kucoin-futures-lib"

    with pytest.raises(ManifestValidationError, match="must map to"):
        validate_library_manifest(manifest_data, allowlist_path=ALLOWLIST_PATH)


def test_repository_url_must_match_the_exact_canonical_repository_url() -> None:
    manifest_data = valid_manifest()
    manifest_data["repository_url"] = "https://github.com/evgesha9400/kucoin-futures-lib"

    with pytest.raises(ManifestValidationError, match="repository_url must equal"):
        validate_library_manifest(manifest_data, allowlist_path=ALLOWLIST_PATH)


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    manifest_path = tmp_path / "library.yml"
    manifest_path.write_text(
        """
schema_version: 1
repository: evgesha9400/ig-trading-lib
repository: evgesha9400/kucoin-futures-lib
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="duplicate key"):
        load_library_manifest(manifest_path)


def test_release_selection_rejects_an_invalid_commit_sha() -> None:
    with pytest.raises(ManifestValidationError, match="commit"):
        validate_release_selection(
            repository="evgesha9400/ig-trading-lib",
            tag="v1.2.3",
            version="1.2.3",
            commit="deadbeef",
            allowlist_path=ALLOWLIST_PATH,
        )


def test_validation_helper_executes_as_the_workflow_module() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "scripts.validate_library_release",
            "--repository",
            "evgesha9400/ig-trading-lib",
            "--tag",
            "v1.2.3",
            "--version",
            "1.2.3",
            "--commit",
            "a" * 40,
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "Library release validation passed.\n"


def test_validation_helper_accepts_durable_manifest_without_release_selection(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "library.yml"
    manifest_path.write_text(json.dumps(valid_manifest()), encoding="utf-8")

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "scripts.validate_library_release",
            "--manifest",
            str(manifest_path),
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "Library manifest validation passed.\n"


def test_rebuild_workflow_validates_hostile_inputs_before_portal_writes() -> None:
    workflow = REBUILD_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "repository_dispatch:" not in workflow
    assert "repository:" in workflow
    assert "tag:" in workflow
    assert "version:" in workflow
    assert "commit:" in workflow
    assert '--repository "$LIBRARY_REPOSITORY"' in workflow
    assert "scripts.validate_library_release" in workflow
    assert workflow.index("scripts.validate_library_release") < workflow.index("gh api")
    assert '"$GITHUB_REF" != "refs/heads/main"' in workflow
    assert "scripts.library_release_publication" in workflow
    assert "git clone" not in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "LIBRARY_PORTAL_DISPATCH_TOKEN" not in workflow


def test_pages_credentials_are_limited_to_deploy_jobs() -> None:
    for workflow_path in (DEPLOY_WORKFLOW_PATH, REBUILD_WORKFLOW_PATH):
        workflow = workflow_path.read_text(encoding="utf-8")
        build_job = workflow[workflow.index("  build:") : workflow.index("  deploy:")]
        deploy_job = workflow[workflow.index("  deploy:") :]

        assert "contents: read" in build_job
        assert "pages: write" not in build_job
        assert "id-token: write" not in build_job
        assert "pages: write" in deploy_job
        assert "id-token: write" in deploy_job
        assert "name: github-pages" in deploy_job


def test_contract_documentation_names_the_future_dispatch_secret_and_scope() -> None:
    documentation = CONTRACT_DOCUMENTATION_PATH.read_text(encoding="utf-8")

    assert "`LIBRARY_PORTAL_DISPATCH_TOKEN`" in documentation
    assert "`Actions: write`" in documentation
    assert "never fetches, renders, executes, imports, or deploys" in documentation
    assert "`library_id`" in documentation
    assert "`package.name`" in documentation
    assert "`repository_url`" in documentation
    assert "## Release event selection" in documentation
    assert "self-referential to a future release tag or commit" in documentation
    assert "## Release publication ingress" in documentation
    assert "published and non-draft" in documentation
