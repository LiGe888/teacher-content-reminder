from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import re


WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value or "").strip()


def clean_block(value: str) -> str:
    lines = [clean_text(line) for line in (value or "").splitlines()]
    filtered = [line for line in lines if line]
    return "\n".join(filtered)


def hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsers = (
        lambda item: datetime.fromisoformat(item),
        lambda item: parsedate_to_datetime(item),
    )
    for parser in parsers:
        try:
            parsed = parser(normalized)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def slugify(value: str, default: str = "item") -> str:
    normalized = clean_text(value).lower()
    if not normalized:
        return default
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or default
