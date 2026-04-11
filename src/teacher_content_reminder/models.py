from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ArticleCandidate:
    source_name: str
    source_category: str
    url: str
    title: str = ""
    summary: str = ""
    published_at: datetime | None = None


@dataclass(slots=True)
class RawArticle:
    source_name: str
    source_category: str
    source_url: str
    canonical_url: str
    title: str
    author: str = ""
    published_at: datetime | None = None
    excerpt: str = ""
    lead_image_url: str = ""
    raw_html: str = ""
    raw_text: str = ""
    word_count: int = 0
    fetched_at: datetime | None = None


@dataclass(slots=True)
class ArticleScore:
    freshness_score: float
    interest_score: float
    teachability_score: float
    info_density_score: float
    exercise_potential_score: float
    safety_score: float
    total_score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PreviewItem:
    candidate: ArticleCandidate
    article: RawArticle
    score: ArticleScore


@dataclass(slots=True)
class ExerciseQuestion:
    question_id: str
    question_type: str
    stem: str
    options: list[str]
    answer: str
    explanation: str


@dataclass(slots=True)
class FactSheet:
    topic: str
    angle: str
    summary: str
    key_points: list[str]
    keywords: list[str]
    discussion_points: list[str]
    teaching_value: str


@dataclass(slots=True)
class GeneratedContentPackage:
    audience: str
    exercise_profile: str
    optimized_title: str
    summary: str
    teaching_value: str
    reading_passage: str
    keywords: list[str]
    discussion_points: list[str]
    reading_questions: list[ExerciseQuestion]
    cloze_passage: str
    cloze_questions: list[ExerciseQuestion]
    traceability_notes: list[str]
    task_timings: dict[str, float]
    task_providers: dict[str, str]
    task_models: dict[str, str]
    generator_provider: str
    generator_model: str
    generated_at: datetime
    package_id: int | None = None


@dataclass(slots=True)
class GeneratedPreviewItem:
    preview: PreviewItem
    package: GeneratedContentPackage


@dataclass(slots=True)
class ReviewQueueItem:
    queue_id: int
    package_id: int
    article_url: str
    source_name: str
    audience: str
    exercise_profile: str
    optimized_title: str
    score_total: float
    review_recommendation: str
    status: str
    reviewer_note: str = ""
    export_directory: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    approved_at: datetime | None = None
    sent_at: datetime | None = None


@dataclass(slots=True)
class DeliveryEvent:
    event_id: int
    queue_id: int | None
    package_id: int | None
    channel: str
    status: str
    created_at: datetime | None = None


@dataclass(slots=True)
class ActivityLogEntry:
    log_id: int
    event_type: str
    status: str
    message: str
    source_name: str = ""
    queue_id: int | None = None
    package_id: int | None = None
    payload: dict[str, object] | None = None
    created_at: datetime | None = None
