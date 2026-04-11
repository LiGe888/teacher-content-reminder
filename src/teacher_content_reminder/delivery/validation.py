from __future__ import annotations

from teacher_content_reminder.models import GeneratedPreviewItem
from teacher_content_reminder.utils import clean_text


MAX_MARKDOWN_CHARS = 12000
MAX_TITLE_CHARS = 100


def validate_generated_preview(item: GeneratedPreviewItem) -> None:
    package = item.package
    if not clean_text(package.optimized_title):
        raise ValueError("Generated package title is empty.")
    if not clean_text(package.summary):
        raise ValueError("Generated package summary is empty.")
    if not clean_text(package.reading_passage):
        raise ValueError("Generated package reading passage is empty.")
    if len(package.reading_questions) < 3:
        raise ValueError("Generated package has too few reading questions.")
    if len(package.cloze_questions) < 3:
        raise ValueError("Generated package has too few cloze questions.")


def normalize_title(title: str) -> str:
    cleaned = clean_text(title)
    if len(cleaned) <= MAX_TITLE_CHARS:
        return cleaned
    return cleaned[: MAX_TITLE_CHARS - 3].rstrip() + "..."


def enforce_markdown_limit(title: str, markdown: str) -> tuple[str, str]:
    normalized_title = normalize_title(title)
    if len(markdown) <= MAX_MARKDOWN_CHARS:
        return normalized_title, markdown
    compressed = markdown[: MAX_MARKDOWN_CHARS - 20].rstrip() + "\n\n[truncated]"
    return normalized_title, compressed
