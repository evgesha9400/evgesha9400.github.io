from __future__ import annotations

import http.server
import json
import socketserver
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_DIRECTORY = PROJECT_ROOT / "site"
ARTIFACTS_DIRECTORY = PROJECT_ROOT / "test-results"
VERIFY_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "verify.yml"
DEPLOY_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "deploy-pages.yml"
EXTERNAL_LINKS_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "external-links.yml"
IG_RELEASE_RECORD_PATH = PROJECT_ROOT / "catalog" / "releases" / "ig-trading-lib.json"


class _SiteRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(SITE_DIRECTORY), **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture(scope="session", autouse=True)
def build_documentation_site() -> Iterator[None]:
    subprocess.run(
        ["mkdocs", "build", "--strict"],
        cwd=PROJECT_ROOT,
        check=True,
    )
    yield


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.fixture()
def site_url() -> Iterator[str]:
    with socketserver.TCPServer(("127.0.0.1", 0), _SiteRequestHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_address[1]}"
        finally:
            server.shutdown()
            thread.join()


@pytest.fixture()
def page(browser: Browser) -> Iterator[Page]:
    browser_page = browser.new_page(viewport={"width": 1440, "height": 1000})
    yield browser_page
    browser_page.close()


def test_portal_cards_expose_source_and_package_links(page: Page, site_url: str) -> None:
    release_record = json.loads(IG_RELEASE_RECORD_PATH.read_text(encoding="utf-8"))
    release_version = release_record["version"]
    documentation_url = release_record["documentation_url"]

    page.goto(site_url, wait_until="networkidle")

    expect(page).to_have_title("Evgeny Aleshin")
    expect(page.get_by_role("heading", name="IG Trading Library")).to_be_visible()
    expect(page.get_by_role("heading", name="KuCoin Futures Library")).to_be_visible()
    expect(
        page.get_by_text(f"documentation available · v{release_version}", exact=True)
    ).to_be_visible()
    expect(page.get_by_text("documentation forthcoming", exact=True)).to_be_visible()

    ig_card = page.locator("[data-library='ig-trading-lib']")
    kucoin_card = page.locator("[data-library='kucoin-futures-lib']")

    expect(ig_card.get_by_role("link", name="Source code")).to_have_attribute(
        "href", "https://github.com/evgesha9400/ig-trading-lib"
    )
    expect(ig_card.get_by_role("link", name="Package on PyPI")).to_have_attribute(
        "href", "https://pypi.org/project/ig-trading-lib/"
    )
    expect(ig_card.get_by_role("link", name=f"Documentation v{release_version}")).to_have_attribute(
        "href", documentation_url
    )
    expect(kucoin_card.get_by_role("link", name="Source code")).to_have_attribute(
        "href", "https://github.com/evgesha9400/kucoin-futures-lib"
    )
    expect(kucoin_card.get_by_role("link", name="Package on PyPI")).to_have_attribute(
        "href", "https://pypi.org/project/kucoin-futures-lib/"
    )


def test_portal_supports_skip_navigation_and_theme_switching(page: Page, site_url: str) -> None:
    page.goto(site_url, wait_until="networkidle")

    skip_link = page.locator(".md-skip")
    skip_target = skip_link.get_attribute("href")
    assert skip_target is not None
    expect(page.locator(skip_target)).to_be_visible()
    theme_switch = page.get_by_title("Switch to dark mode")
    expect(theme_switch).to_be_visible()

    theme_switch.click()
    expect(page.locator("body")).to_have_attribute("data-md-color-scheme", "slate")


def test_portal_has_a_single_column_mobile_layout(page: Page, site_url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(site_url, wait_until="networkidle")

    ig_card = page.locator("[data-library='ig-trading-lib']")
    kucoin_card = page.locator("[data-library='kucoin-futures-lib']")
    ig_box = ig_card.bounding_box()
    kucoin_box = kucoin_card.bounding_box()

    assert ig_box is not None
    assert kucoin_box is not None
    assert kucoin_box["y"] > ig_box["y"]
    assert ig_box["x"] >= 0
    assert ig_box["x"] + ig_box["width"] <= 390
    assert kucoin_box["x"] + kucoin_box["width"] <= 390
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    ARTIFACTS_DIRECTORY.mkdir(exist_ok=True)
    screenshot_path = ARTIFACTS_DIRECTORY / "portal-mobile.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    assert screenshot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_home_prototype_index_links_all_three_directions(page: Page, site_url: str) -> None:
    page.goto(f"{site_url}/prototypes/", wait_until="networkidle")

    prototype_links = page.locator("[data-prototype-link]")
    expect(prototype_links).to_have_count(3)
    expect(page.get_by_role("link", name="Explore editorial registry")).to_have_attribute(
        "href", "editorial-registry/"
    )
    expect(page.get_by_role("link", name="Explore systems console")).to_have_attribute(
        "href", "systems-console/"
    )
    expect(page.get_by_role("link", name="Explore library constellation")).to_have_attribute(
        "href", "library-constellation/"
    )


@pytest.mark.parametrize(
    ("route", "prototype_name", "heading"),
    [
        (
            "editorial-registry",
            "editorial",
            "Open-source Python libraries.",
        ),
        ("systems-console", "console", "Two libraries. One reliable interface."),
        ("library-constellation", "constellation", "Find the right library by orbit."),
    ],
)
def test_home_prototypes_are_distinct_accessible_library_indexes(
    page: Page,
    site_url: str,
    route: str,
    prototype_name: str,
    heading: str,
) -> None:
    page.goto(f"{site_url}/prototypes/{route}/", wait_until="networkidle")

    prototype = page.locator(f"[data-prototype='{prototype_name}']")
    expect(prototype).to_be_visible()
    expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
    expect(prototype.get_by_text("IG Trading Library", exact=True)).to_be_visible()
    expect(prototype.get_by_text("KuCoin Futures Library", exact=True)).to_be_visible()
    documentation_link = prototype.get_by_role("link", name="IG documentation", exact=True)
    source_link = prototype.get_by_role("link", name="IG source", exact=True)
    if prototype_name == "editorial":
        documentation_link = prototype.get_by_role(
            "link", name="IG Trading Library Documentation", exact=True
        )
        source_link = prototype.get_by_role("link", name="IG Trading Library Source", exact=True)
    expect(documentation_link).to_have_attribute(
        "href", "https://evgesha9400.github.io/ig-trading-lib/latest/"
    )
    expect(source_link).to_have_attribute("href", "https://github.com/evgesha9400/ig-trading-lib")

    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="networkidle")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    mobile_heading = page.get_by_role("heading", name=heading, exact=True)
    assert mobile_heading.evaluate("element => element.scrollWidth <= element.clientWidth")


def test_editorial_prototype_has_release_provenance_and_a_real_dark_theme(
    page: Page, site_url: str
) -> None:
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    prototype = page.locator("[data-prototype='editorial']")
    expect(prototype.get_by_text("Public code · released packages", exact=True)).to_be_visible()
    light_background = prototype.evaluate("element => getComputedStyle(element).backgroundColor")
    light_foreground = prototype.evaluate("element => getComputedStyle(element).color")

    page.get_by_title("Switch to dark mode").click()
    expect(page.locator("body")).to_have_attribute("data-md-color-scheme", "slate")
    dark_background = prototype.evaluate("element => getComputedStyle(element).backgroundColor")
    dark_foreground = prototype.evaluate("element => getComputedStyle(element).color")

    assert dark_background != light_background
    assert dark_foreground != light_foreground

    ARTIFACTS_DIRECTORY.mkdir(exist_ok=True)
    screenshot_path = ARTIFACTS_DIRECTORY / "prototype-editorial-dark.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    assert screenshot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="networkidle")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    ig_documentation = prototype.get_by_role(
        "link", name="IG Trading Library Documentation", exact=True
    )
    ig_documentation.focus()
    assert ig_documentation.evaluate("element => getComputedStyle(element).outlineStyle") != "none"


def test_editorial_prototype_is_a_personal_open_source_portfolio(page: Page, site_url: str) -> None:
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    prototype = page.locator("[data-prototype='editorial']")
    expect(
        prototype.get_by_text("Evgeny Aleshin · Maintained open-source projects")
    ).to_be_visible()
    expect(
        prototype.get_by_text("A catalogue of Python libraries I maintain", exact=False)
    ).to_be_visible()
    expect(prototype.get_by_role("heading", name="Catalogue status")).to_be_visible()
    expect(prototype.get_by_role("heading", name="Public repositories")).to_be_visible()
    expect(prototype.get_by_role("heading", name="PyPI packages")).to_be_visible()
    expect(prototype.get_by_role("heading", name="Published documentation")).to_be_visible()
    expect(prototype.get_by_text("Both projects are public on GitHub.", exact=True)).to_be_visible()
    expect(
        prototype.get_by_text("Both projects are distributed through PyPI.", exact=True)
    ).to_be_visible()
    expect(
        prototype.get_by_text(
            "Versioned documentation is published for IG Trading Library", exact=False
        )
    ).to_be_visible()
    expect(
        prototype.get_by_role("link", name="IG Trading Library Package", exact=True)
    ).to_have_attribute("href", "https://pypi.org/project/ig-trading-lib/")
    expect(
        prototype.get_by_role("link", name="KuCoin Futures Library Package", exact=True)
    ).to_have_attribute("href", "https://pypi.org/project/kucoin-futures-lib/")
    expect(
        prototype.get_by_role("link", name="KuCoin Futures Library Source", exact=True)
    ).to_have_attribute("href", "https://github.com/evgesha9400/kucoin-futures-lib")
    expect(prototype.get_by_role("link", name="More work on GitHub")).to_have_attribute(
        "href", "https://github.com/evgesha9400"
    )
    expect(prototype.get_by_text("Prototype 01 / Editorial", exact=True)).to_have_count(0)
    expect(prototype.get_by_text("Compare all directions", exact=False)).to_have_count(0)


def test_editorial_prototype_keeps_large_desktop_sections_compact(
    page: Page, site_url: str
) -> None:
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    hero = page.locator(".editorial-hero").bounding_box()
    practice = page.locator(".editorial-practice").bounding_box()
    entries = page.locator(".editorial-entry")

    assert hero is not None
    assert practice is not None
    assert hero["height"] <= 560
    assert practice["height"] <= 300
    for index in range(entries.count()):
        entry = entries.nth(index).bounding_box()
        assert entry is not None
        assert entry["height"] <= 400

    heading_size = page.locator(".editorial-hero h1").evaluate(
        "element => parseFloat(getComputedStyle(element).fontSize)"
    )
    heading_line_height = page.locator(".editorial-hero h1").evaluate(
        "element => parseFloat(getComputedStyle(element).lineHeight)"
    )
    assert heading_size <= 120
    assert heading_line_height >= heading_size * 0.9


@pytest.mark.parametrize(
    ("library_id", "command"),
    [
        ("ig-trading-lib", "pip install ig-trading-lib"),
        ("kucoin-futures-lib", "pip install kucoin-futures-lib"),
    ],
)
def test_editorial_install_commands_are_highlighted_and_copyable(
    page: Page, site_url: str, library_id: str, command: str
) -> None:
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=site_url)
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    install = page.locator(f"[data-library='{library_id}'] .editorial-install")
    expect(install.locator(".language-shell")).to_contain_text(command)
    copy_button = install.get_by_title("Copy to clipboard")
    expect(copy_button).to_be_visible()

    copy_button.click()
    page.wait_for_timeout(100)
    assert page.evaluate("navigator.clipboard.readText()") == command


def test_portal_mobile_card_layout_produces_a_visual_artifact(page: Page, site_url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(site_url, wait_until="networkidle")
    page.add_style_tag(
        content="""
        .portal-grid { grid-template-columns: 1fr !important; }
        .portal-card { box-sizing: border-box; height: 20rem; }
        .portal-card * { visibility: hidden !important; }
        """
    )

    ARTIFACTS_DIRECTORY.mkdir(exist_ok=True)
    screenshot_path = ARTIFACTS_DIRECTORY / "portal-card-layout-mobile.png"
    page.locator(".portal-grid").screenshot(path=str(screenshot_path))

    assert screenshot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_custom_not_found_page_is_available(site_url: str) -> None:
    result = subprocess.run(
        ["curl", "--fail", "--silent", f"{site_url}/404.html"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Page not found" in result.stdout
    assert "Return to the documentation portal" in result.stdout


def test_workflows_keep_deterministic_and_remote_link_checks_separate() -> None:
    verify_workflow = VERIFY_WORKFLOW_PATH.read_text(encoding="utf-8")
    deploy_workflow = DEPLOY_WORKFLOW_PATH.read_text(encoding="utf-8")
    external_links_workflow = EXTERNAL_LINKS_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "actions/checkout@v5" in verify_workflow
    assert "actions/setup-python@v6" in verify_workflow
    assert "astral-sh/setup-uv@v8.3.2" in verify_workflow
    assert "actions/upload-artifact@v7" in verify_workflow
    assert "lycheeverse/lychee-action" not in verify_workflow
    assert "actions/checkout@v5" in deploy_workflow
    assert "actions/setup-python@v6" in deploy_workflow
    assert "actions/upload-pages-artifact@v4" in deploy_workflow
    assert "astral-sh/setup-uv@v8.3.2" in deploy_workflow
    assert "schedule:" in external_links_workflow
    assert "lycheeverse/lychee-action@v2" in external_links_workflow
    assert "--exclude-all-private" in external_links_workflow
