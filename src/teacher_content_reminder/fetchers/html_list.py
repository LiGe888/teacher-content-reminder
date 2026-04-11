from __future__ import annotations

from collections import OrderedDict
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from teacher_content_reminder.config import SourceConfig
from teacher_content_reminder.fetchers.base import SourceFetcher
from teacher_content_reminder.models import ArticleCandidate
from teacher_content_reminder.network import fetch_text
from teacher_content_reminder.utils import clean_text


class HTMLListFetcher(SourceFetcher):
    def fetch(self, source: SourceConfig, limit: int = 10) -> list[ArticleCandidate]:
        response = fetch_text(source.entry_url)
        parser = LinkDiscoveryParser(base_url=response.url)
        parser.feed(response.text)

        filtered = OrderedDict()
        for href, text in parser.links:
            candidate_url = urljoin(response.url, href)
            if not _looks_like_article_url(candidate_url, source.entry_url):
                continue
            label = clean_text(text)
            if len(label) < 20:
                continue
            filtered[candidate_url] = label

        items = list(filtered.items())[:limit]
        return [
            ArticleCandidate(
                source_name=source.name,
                source_category=source.category,
                url=url,
                title=title,
            )
            for url, title in items
        ]


class LinkDiscoveryParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        text = clean_text(" ".join(self._current_text))
        self.links.append((self._current_href, text))
        self._current_href = None
        self._current_text = []


def _looks_like_article_url(candidate_url: str, base_url: str) -> bool:
    parsed_candidate = urlparse(candidate_url)
    parsed_base = urlparse(base_url)
    if parsed_candidate.scheme not in {"http", "https"}:
        return False
    if parsed_candidate.netloc != parsed_base.netloc:
        return False
    if not parsed_candidate.path or parsed_candidate.path in {"/", ""}:
        return False
    if "#" in candidate_url:
        return False
    path = parsed_candidate.path.lower()
    blocked = ("/tag/", "/topics/", "/author/", "/about/", "/contact/", "/newsletters/", "/video/")
    if any(segment in path for segment in blocked):
        return False
    return len(path.strip("/").split("/")) >= 1

