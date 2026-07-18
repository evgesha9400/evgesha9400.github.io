from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

LINK_ATTRIBUTES = {"a": "href", "img": "src", "link": "href", "script": "src"}
EXTERNAL_SCHEMES = {"data", "http", "https", "javascript", "mailto", "tel"}


@dataclass
class HtmlDocument:
    path: Path
    identifiers: set[str] = field(default_factory=set)
    links: list[str] = field(default_factory=list)


class DocumentParser(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.document = HtmlDocument(path=path)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        identifier = attributes.get("id")
        if identifier:
            self.document.identifiers.add(identifier)

        link_attribute = LINK_ATTRIBUTES.get(tag)
        link = attributes.get(link_attribute) if link_attribute else None
        if link:
            self.document.links.append(link)


def parse_document(path: Path) -> HtmlDocument:
    parser = DocumentParser(path)
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.document


def resolve_target(site_directory: Path, source_path: Path, link_path: str) -> Path | None:
    decoded_path = unquote(link_path)
    if not decoded_path:
        return source_path

    target = (
        site_directory / decoded_path.lstrip("/")
        if decoded_path.startswith("/")
        else source_path.parent / decoded_path
    )
    candidates = [target]
    if target.suffix == "":
        candidates.extend((target / "index.html", target.with_suffix(".html")))

    return next((candidate for candidate in candidates if candidate.is_file()), None)


def find_link_errors(site_directory: Path) -> list[str]:
    documents = {path: parse_document(path) for path in site_directory.rglob("*.html")}
    errors: list[str] = []

    for document in documents.values():
        for link in document.links:
            parsed_link = urlsplit(link)
            if parsed_link.scheme in EXTERNAL_SCHEMES or parsed_link.netloc:
                continue

            target = resolve_target(site_directory, document.path, parsed_link.path)
            if target is None:
                errors.append(f"{document.path.relative_to(site_directory)}: missing target {link}")
                continue

            if parsed_link.fragment and target.suffix == ".html":
                target_document = documents.get(target) or parse_document(target)
                fragment = unquote(parsed_link.fragment)
                if fragment not in target_document.identifiers:
                    errors.append(
                        f"{document.path.relative_to(site_directory)}: missing anchor {link}"
                    )

    return errors


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check generated documentation links and anchors.")
    parser.add_argument("--site", type=Path, required=True, help="Generated MkDocs site directory.")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    site_directory = arguments.site.resolve()
    if not site_directory.is_dir():
        raise SystemExit(f"Generated site directory does not exist: {site_directory}")

    errors = find_link_errors(site_directory)
    if errors:
        raise SystemExit("\n".join(errors))

    print(f"Verified local links and anchors in {site_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
