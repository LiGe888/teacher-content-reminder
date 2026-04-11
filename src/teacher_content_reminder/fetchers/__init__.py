from teacher_content_reminder.fetchers.base import SourceFetcher
from teacher_content_reminder.fetchers.html_list import HTMLListFetcher
from teacher_content_reminder.fetchers.rss import RSSFetcher


FETCHERS: dict[str, SourceFetcher] = {
    "rss": RSSFetcher(),
    "html_list": HTMLListFetcher(),
}


def get_fetcher(source_type: str) -> SourceFetcher:
    try:
        return FETCHERS[source_type]
    except KeyError as exc:
        raise KeyError(f"Unsupported source type: {source_type}") from exc

