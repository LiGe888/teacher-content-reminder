from __future__ import annotations

import json
try:
    import trafilatura
except ImportError as exc:
    raise RuntimeError("trafilatura is not installed. Please run `pip install trafilatura`.") from exc

from teacher_content_reminder.models import RawArticle
from teacher_content_reminder.network import fetch_text
from teacher_content_reminder.utils import clean_block, clean_text, parse_datetime, utc_now


class HTMLArticleExtractor:
    def extract(self, url: str, source_name: str, source_category: str) -> RawArticle:
        response = fetch_text(url)
        json_output = trafilatura.extract(
            response.text,
            include_links=False,
            include_images=False,
            output_format="json",
            with_metadata=True
        )

        if not json_output:
            raise ValueError(f"Unable to extract article structure from {url}")

        data = json.loads(json_output)
        raw_text = clean_block(data.get("text") or "")
        if not raw_text:
            # Fallback for sites where Trafilatura might return empty text if blocks are weird
            raise ValueError(f"Unable to extract main article text from {url}")

        title = data.get("title") or "Untitled Article"
        excerpt = data.get("description") or data.get("excerpt") or raw_text[:240]
        published_at = parse_datetime(data.get("date") or "")

        return RawArticle(
            source_name=source_name,
            source_category=source_category,
            source_url=url,
            canonical_url=data.get("source") or data.get("url") or response.url,
            title=clean_text(title),
            author=clean_text(data.get("author") or ""),
            published_at=published_at,
            excerpt=clean_text(excerpt),
            lead_image_url=data.get("image") or "",
            raw_html=response.text,
            raw_text=raw_text,
            word_count=len(raw_text.split()),
            fetched_at=utc_now(),
        )
