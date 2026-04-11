from __future__ import annotations

from xml.etree import ElementTree

from teacher_content_reminder.config import SourceConfig
from teacher_content_reminder.models import ArticleCandidate
from teacher_content_reminder.network import fetch_text
from teacher_content_reminder.utils import clean_text, parse_datetime
from teacher_content_reminder.fetchers.base import SourceFetcher


class RSSFetcher(SourceFetcher):
    def fetch(self, source: SourceConfig, limit: int = 10) -> list[ArticleCandidate]:
        response = fetch_text(source.entry_url)
        root = ElementTree.fromstring(response.text)
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        candidates: list[ArticleCandidate] = []
        for item in items[:limit]:
            title = _find_text(item, "title")
            link = _find_link(item)
            if not link:
                continue
            published = parse_datetime(
                _find_text(item, "pubDate")
                or _find_text(item, "published")
                or _find_text(item, "updated")
            )
            summary = _find_text(item, "description") or _find_text(item, "summary")
            candidates.append(
                ArticleCandidate(
                    source_name=source.name,
                    source_category=source.category,
                    url=link,
                    title=clean_text(title),
                    summary=clean_text(summary),
                    published_at=published,
                )
            )
        return candidates


def _find_text(node: ElementTree.Element, tag_name: str) -> str:
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1] == tag_name:
            return child.text or ""
    return ""


def _find_link(node: ElementTree.Element) -> str:
    direct = _find_text(node, "link")
    if direct:
        return direct.strip()

    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1] != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href.strip()
    return ""

