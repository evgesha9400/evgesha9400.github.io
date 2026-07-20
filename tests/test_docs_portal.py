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
    expect(prototype.get_by_text("Open-source libraries", exact=True)).to_be_visible()
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
    expect(prototype.locator(".prototype-bar")).to_have_count(0)


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
    assert heading_line_height >= heading_size * 1.02


def test_editorial_wide_heading_does_not_overlap(page: Page, site_url: str) -> None:
    page.set_viewport_size({"width": 2648, "height": 1354})
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    heading = page.locator(".editorial-hero h1")
    typography = heading.evaluate(
        """element => ({
            fontSize: parseFloat(getComputedStyle(element).fontSize),
            lineHeight: parseFloat(getComputedStyle(element).lineHeight),
        })"""
    )

    assert typography["fontSize"] <= 132
    assert typography["lineHeight"] >= typography["fontSize"] * 1.02


@pytest.mark.parametrize("viewport_width", [1440, 2648])
def test_editorial_theme_toggle_remains_discoverable(
    page: Page, site_url: str, viewport_width: int
) -> None:
    page.set_viewport_size({"width": viewport_width, "height": 900})
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    dark_mode = page.get_by_title("Switch to dark mode")
    expect(dark_mode).to_be_visible()
    boundary = dark_mode.evaluate(
        """element => ({
            borderWidth: parseFloat(getComputedStyle(element).borderTopWidth),
            opacity: Number(getComputedStyle(element).opacity),
        })"""
    )
    assert boundary["borderWidth"] >= 1
    assert boundary["opacity"] == 1

    search_box = page.locator(".md-search").bounding_box()
    toggle_box = dark_mode.bounding_box()
    assert search_box is not None
    assert toggle_box is not None
    assert search_box["x"] + search_box["width"] + 8 <= toggle_box["x"]

    page.get_by_role("textbox", name="Search").click()
    page.wait_for_timeout(250)
    focused_search_box = page.locator(".md-search__form").bounding_box()
    focused_toggle_box = dark_mode.bounding_box()
    focused_source_box = page.locator(".md-header__source").bounding_box()
    focused_toggle_opacity = page.locator(".md-header__option").evaluate(
        "element => Number(getComputedStyle(element).opacity)"
    )
    assert focused_search_box is not None
    assert focused_toggle_box is not None
    assert focused_source_box is not None
    assert focused_toggle_opacity == 1
    assert focused_toggle_box["width"] >= 32
    assert focused_search_box["x"] + focused_search_box["width"] + 8 <= focused_toggle_box["x"]
    assert focused_toggle_box["x"] + focused_toggle_box["width"] + 8 <= focused_source_box["x"]

    dark_mode.click()
    expect(page.locator("body")).to_have_attribute("data-md-color-scheme", "slate")
    expect(page.get_by_title("Switch to light mode")).to_be_visible()


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


@pytest.mark.parametrize("scheme", ["default", "slate"])
def test_editorial_copy_control_has_accessible_contrast(
    page: Page, site_url: str, scheme: str
) -> None:
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")
    page.locator("body").evaluate(
        "(element, colorScheme) => element.dataset.mdColorScheme = colorScheme", scheme
    )

    copy_button = page.locator(".editorial-install .md-code__button").first
    contrast = copy_button.evaluate(
        """element => {
            const parseRgb = value => value.match(/[\\d.]+/g).slice(0, 3).map(Number)
            const luminance = color => {
                const channels = color.map(value => value / 255).map(
                    value => value <= 0.04045
                        ? value / 12.92
                        : ((value + 0.055) / 1.055) ** 2.4
                )
                return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
            }
            const foreground = luminance(parseRgb(getComputedStyle(element).color))
            const background = luminance(
                parseRgb(getComputedStyle(element.closest('pre')).backgroundColor)
            )
            return {
                opacity: Number(getComputedStyle(element).opacity),
                ratio: (Math.max(foreground, background) + 0.05)
                    / (Math.min(foreground, background) + 0.05),
            }
        }"""
    )

    assert contrast["opacity"] == 1
    assert contrast["ratio"] >= 4.5


def test_editorial_search_joins_rounded_input_and_results(page: Page, site_url: str) -> None:
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    search_input = page.get_by_role("textbox", name="Search")
    closed_form_box = page.locator(".md-search__form").bounding_box()
    search_input.click()
    page.wait_for_timeout(250)
    search_form = page.locator(".md-search__form")
    search_inner = page.locator(".md-search__inner")
    search_output = page.locator(".md-search__output")

    form_radii = search_form.evaluate(
        """element => {
            const style = getComputedStyle(element)
            return [
                style.borderTopLeftRadius,
                style.borderTopRightRadius,
                style.borderBottomRightRadius,
                style.borderBottomLeftRadius,
            ]
        }"""
    )
    output_radii = search_output.evaluate(
        """element => {
            const style = getComputedStyle(element)
            return [
                style.borderTopLeftRadius,
                style.borderTopRightRadius,
                style.borderBottomRightRadius,
                style.borderBottomLeftRadius,
            ]
        }"""
    )

    assert float(form_radii[0].removesuffix("px")) >= 12
    assert float(form_radii[1].removesuffix("px")) >= 12
    assert form_radii[2:] == ["0px", "0px"]
    assert output_radii[:2] == ["0px", "0px"]
    assert output_radii[2] != "0px"
    assert output_radii[3] != "0px"

    form_box = search_form.bounding_box()
    inner_box = search_inner.bounding_box()
    output_box = search_output.bounding_box()
    assert closed_form_box is not None
    assert form_box is not None
    assert inner_box is not None
    assert output_box is not None
    assert abs(form_box["width"] - closed_form_box["width"]) <= 1
    assert abs(inner_box["width"] - closed_form_box["width"]) <= 1
    assert abs(form_box["x"] - output_box["x"]) <= 1
    assert abs(form_box["width"] - output_box["width"]) <= 1
    assert form_box["width"] >= 500
    assert abs(form_box["x"] + form_box["width"] / 2 - 720) <= 1

    ARTIFACTS_DIRECTORY.mkdir(exist_ok=True)
    screenshot_path = ARTIFACTS_DIRECTORY / "editorial-search-open.png"
    page.screenshot(path=str(screenshot_path))
    assert screenshot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_editorial_search_returns_to_pill_after_outside_click(page: Page, site_url: str) -> None:
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    search_form = page.locator(".md-search__form")
    search_output = page.locator(".md-search__output")
    search_toggle = page.locator('[data-md-toggle="search"]')
    closed_radii = search_form.evaluate(
        """element => {
            const style = getComputedStyle(element)
            return [
                style.borderTopLeftRadius,
                style.borderTopRightRadius,
                style.borderBottomRightRadius,
                style.borderBottomLeftRadius,
            ]
        }"""
    )

    page.get_by_role("textbox", name="Search").click()
    page.wait_for_timeout(250)
    page.mouse.click(16, 300)
    page.wait_for_timeout(250)

    returned_radii = search_form.evaluate(
        """element => {
            const style = getComputedStyle(element)
            return [
                style.borderTopLeftRadius,
                style.borderTopRightRadius,
                style.borderBottomRightRadius,
                style.borderBottomLeftRadius,
            ]
        }"""
    )
    output_box = search_output.bounding_box()
    assert output_box is not None
    assert not search_toggle.is_checked()
    assert returned_radii == closed_radii
    assert output_box["height"] == 0


def test_editorial_header_content_aligns_with_page_content(page: Page, site_url: str) -> None:
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(f"{site_url}/prototypes/editorial-registry/", wait_until="networkidle")

    page_content = page.locator(".editorial-hero").bounding_box()
    header_brand = page.locator(".md-header__button.md-logo").bounding_box()
    header_source = page.locator(".md-header__source").bounding_box()

    assert page_content is not None
    assert header_brand is not None
    assert header_source is not None
    assert abs(header_brand["x"] - page_content["x"]) <= 2
    assert (
        abs(header_source["x"] + header_source["width"] - page_content["x"] - page_content["width"])
        <= 2
    )
    assert page_content["width"] <= 1400
    assert abs(page_content["x"] + page_content["width"] / 2 - 960) <= 2


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
