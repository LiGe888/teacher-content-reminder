from __future__ import annotations

from teacher_content_reminder.models import GeneratedPreviewItem
from teacher_content_reminder.delivery.validation import enforce_markdown_limit, validate_generated_preview


def render_dingtalk_markdown(item: GeneratedPreviewItem) -> tuple[str, str]:
    validate_generated_preview(item)
    package = item.package
    article = item.preview.article
    title = package.optimized_title

    lines = [
        f"# {title}",
        "",
        f"> Audience: {package.audience} | Source: {article.source_name} | Score: {item.preview.score.total_score}",
    ]

    # Use lead image if available; fall back to a topic-relevant placeholder
    image_url = article.lead_image_url
    if not image_url or not _is_likely_loadable(image_url):
        image_url = _fallback_image_url(article.source_category)
    if image_url:
        lines.extend(["", f"![cover]({image_url})"])

    lines.extend(
        [
            "",
            "## Summary",
            package.summary,
            "",
            "## Teaching Value",
            package.teaching_value,
            "",
            "## Keywords",
            ", ".join(package.keywords),
            "",
            "## Reading Passage",
            _truncate_block(package.reading_passage, max_words=220),
            "",
            "## Reading Questions",
        ]
    )

    for index, question in enumerate(package.reading_questions, start=1):
        lines.append(f"**{index}. {question.stem}**")
        lines.append("")
        for option in question.options:
            lines.append(f"- {option}")
        lines.append("")
        lines.append(f"✅ Answer: **{question.answer}**")
        if question.explanation:
            lines.append(f"💡 {question.explanation[:150]}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.extend(
        [
            "## Cloze",
            _truncate_block(package.cloze_passage, max_words=180),
            "",
            "## Cloze Answers",
            "",
        ]
    )
    for question in package.cloze_questions[:8]:
        answer_text = ""
        for option in question.options:
            if option.upper().startswith(f"{question.answer}."):
                answer_text = option
                break
        lines.append(f"- **({question.question_id})** {answer_text}")

    lines.extend(
        [
            "",
            "## Source",
            f"[Open original article]({article.canonical_url})",
        ]
    )

    import os
    base_url = os.environ.get("ALERT_VIEW_HOST", "").rstrip("/")
    if base_url:
        from teacher_content_reminder.utils import slugify
        date_segment = package.generated_at.date().isoformat()
        source_segment = slugify(article.source_name, default="source")
        title_segment = slugify(package.optimized_title, default="worksheet")
        
        student_url = f"{base_url}/exports/{date_segment}/{source_segment}/{title_segment}/student_worksheet.html"
        teacher_url = f"{base_url}/exports/{date_segment}/{source_segment}/{title_segment}/teacher_worksheet.html"
        
        lines.extend([
            "",
            "---",
            "## 📄 附件与打印",
            f"🔗 [🧑‍🎓 学生版试卷 (无答案)]({student_url})",
            f"🔗 [🧑‍🏫 教师版试卷 (含答案)]({teacher_url})"
        ])

    text = "\n".join(lines)
    return enforce_markdown_limit(title, text)


def _truncate_block(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " ..."


def _is_likely_loadable(url: str) -> bool:
    """Quick heuristic check if an image URL is likely to load in DingTalk."""
    if not url or not url.startswith("http"):
        return False
    # Block known problematic patterns
    blocked = [".gov/wp-content/", "cms.gov", "localhost"]
    return not any(b in url for b in blocked)


# Stable, high-quality topic images (Unsplash direct links, no API key needed)
_FALLBACK_IMAGES = {
    "science_nature": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
    "current_events": "https://images.unsplash.com/photo-1504711434969-e33886168d5c?w=800&q=80",
    "culture_history": "https://images.unsplash.com/photo-1461360370896-922624d12a74?w=800&q=80",
}


def _fallback_image_url(category: str) -> str:
    """Return a stable, high-quality fallback image URL based on article category."""
    return _FALLBACK_IMAGES.get(category, _FALLBACK_IMAGES["science_nature"])
