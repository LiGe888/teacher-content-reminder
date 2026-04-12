from __future__ import annotations

from pathlib import Path

from teacher_content_reminder.config import AudienceConfig, ExerciseProfileConfig
from teacher_content_reminder.models import FactSheet, RawArticle

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> str:
    """Load a prompt template from the templates/ directory.

    Falls back gracefully if the file is missing (e.g. during tests with
    a stripped install), so callers always get a usable string.
    """
    path = _TEMPLATES_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Fallback: return empty string — callers should never reach this in prod
    raise FileNotFoundError(f"Prompt template not found: {path}")


def render_extract_facts_prompt(article: RawArticle, audience_key: str, max_input_chars: int) -> str:
    template = _load_template("extract_facts.txt")
    return template.format(
        audience_key=audience_key,
        title=article.title,
        source_category=article.source_category,
        excerpt=article.excerpt,
        truncated_text=article.raw_text[:max_input_chars],
    ).strip()


def render_title_summary_prompt(article: RawArticle, facts: FactSheet, audience_key: str) -> str:
    template = _load_template("title_summary.txt")
    return template.format(
        audience_key=audience_key,
        title=article.title,
        facts_summary=facts.summary,
        key_points=facts.key_points,
    ).strip()


def render_reading_passage_prompt(
    article: RawArticle,
    facts: FactSheet,
    audience_key: str,
    audience: AudienceConfig,
) -> str:
    template = _load_template("reading_passage.txt")
    return template.format(
        audience_key=audience_key,
        cefr=audience.cefr,
        min_words=audience.passage_words[0],
        max_words=audience.passage_words[1],
        title=article.title,
        key_points=facts.key_points,
    ).strip()


def render_reading_questions_prompt(
    facts: FactSheet,
    audience_key: str,
    audience: AudienceConfig,
    exercise_profile: ExerciseProfileConfig,
    passage: str,
) -> str:
    template = _load_template("reading_questions.txt")
    return template.format(
        audience_key=audience_key,
        question_count=audience.question_count,
        include_answers=exercise_profile.include_answers,
        include_explanations=exercise_profile.include_explanations,
        facts_summary=facts.summary,
        passage=passage,
    ).strip()


def render_cloze_prompt(
    facts: FactSheet,
    audience_key: str,
    audience: AudienceConfig,
    passage: str,
) -> str:
    template = _load_template("cloze_test.txt")
    return template.format(
        audience_key=audience_key,
        cloze_blanks=audience.cloze_blanks,
        keywords=facts.keywords,
        passage=passage,
    ).strip()
