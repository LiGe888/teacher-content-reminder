from __future__ import annotations

from datetime import timedelta
from typing import Any

from teacher_content_reminder.models import ArticleScore, RawArticle
from teacher_content_reminder.utils import utc_now


# Default keyword sets — can be overridden via ScoringConfig
_DEFAULT_INTEREST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "science_nature": ("space", "nasa", "brain", "animal", "climate", "discovery", "quantum", "ocean"),
    "culture_history": ("history", "culture", "ancient", "museum", "roman", "artifact", "tradition"),
    "current_events": ("school", "community", "technology", "breakthrough", "global", "education", "health"),
}

_DEFAULT_SAFETY_BLOCKLIST: tuple[str, ...] = (
    "graphic",
    "beheaded",
    "massacre",
    "porn",
    "lottery",
    "celebrity scandal",
)

# Discourse connectors that signal exercise potential
_DISCOURSE_CONNECTORS: tuple[str, ...] = (
    "because", "however", "but", "after", "before", "while",
    "therefore", "although", "despite", "furthermore", "consequently",
)

# Legacy module-level names kept for backward compatibility
INTEREST_KEYWORDS = _DEFAULT_INTEREST_KEYWORDS
SAFETY_BLOCKLIST = _DEFAULT_SAFETY_BLOCKLIST


class ScoringConfig:
    """Holds tunable scoring parameters so they can be driven from config/TOML."""

    def __init__(
        self,
        interest_keywords: dict[str, tuple[str, ...]] | None = None,
        safety_blocklist: tuple[str, ...] | None = None,
        weights: dict[str, float] | None = None,
        safety_penalty_per_hit: float = 25.0,
    ) -> None:
        self.interest_keywords: dict[str, tuple[str, ...]] = (
            interest_keywords if interest_keywords is not None else _DEFAULT_INTEREST_KEYWORDS
        )
        self.safety_blocklist: tuple[str, ...] = (
            safety_blocklist if safety_blocklist is not None else _DEFAULT_SAFETY_BLOCKLIST
        )
        # Weights must sum to 1.0; defaults match original hard-coded values
        self.weights: dict[str, float] = weights or {
            "freshness": 0.25,
            "interest": 0.20,
            "teachability": 0.25,
            "info_density": 0.15,
            "exercise_potential": 0.15,
        }
        self.safety_penalty_per_hit = safety_penalty_per_hit

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoringConfig":
        """Build from a plain dict (e.g. loaded from TOML)."""
        keywords_raw = data.get("interest_keywords", {})
        interest_keywords = {k: tuple(v) for k, v in keywords_raw.items()} if keywords_raw else None
        blocklist_raw = data.get("safety_blocklist")
        safety_blocklist = tuple(blocklist_raw) if blocklist_raw else None
        weights_raw = data.get("weights")
        weights = dict(weights_raw) if weights_raw else None
        return cls(
            interest_keywords=interest_keywords,
            safety_blocklist=safety_blocklist,
            weights=weights,
            safety_penalty_per_hit=float(data.get("safety_penalty_per_hit", 25.0)),
        )


# Module-level default instance used by score_article()
_default_scoring_config = ScoringConfig()



def score_article(article: RawArticle, scoring_config: ScoringConfig | None = None) -> ArticleScore:
    cfg = scoring_config or _default_scoring_config
    text_blob = f"{article.title} {article.excerpt} {article.raw_text}".lower()
    reasons: list[str] = []

    freshness_score = _score_freshness(article)
    if freshness_score >= 90:
        reasons.append("内容发布时间非常新，适合进入今日候选池。")
    elif freshness_score >= 70:
        reasons.append("内容仍在有效时效窗口内。")
    else:
        reasons.append("内容时效性一般，但仍可作为补充素材。")

    keyword_hits = sum(
        keyword in text_blob
        for keyword in cfg.interest_keywords.get(article.source_category, ())
    )
    interest_score = min(100.0, 55.0 + keyword_hits * 9.0)
    if keyword_hits:
        reasons.append("命中了与目标主题相关的趣味关键词。")

    teachability_score = 45.0
    if 120 <= article.word_count <= 900:
        teachability_score += 35.0
    elif 901 <= article.word_count <= 1400:
        teachability_score += 20.0
    if article.excerpt:
        teachability_score += 10.0
    if article.lead_image_url:
        teachability_score += 10.0

    paragraph_count = article.raw_text.count("\n\n") + 1
    info_density_score = min(100.0, 35.0 + paragraph_count * 8.0 + min(article.word_count, 600) / 12.0)

    exercise_potential_score = 40.0
    if article.word_count >= 180:
        exercise_potential_score += 20.0
    if any(token in text_blob for token in _DISCOURSE_CONNECTORS):
        exercise_potential_score += 20.0
    if any(char.isdigit() for char in article.raw_text):
        exercise_potential_score += 10.0
    if paragraph_count >= 4:
        exercise_potential_score += 10.0
    exercise_potential_score = min(100.0, exercise_potential_score)

    safety_hits = [kw for kw in cfg.safety_blocklist if kw in text_blob]
    safety_penalty = len(safety_hits) * cfg.safety_penalty_per_hit
    safety_score = max(0.0, 100.0 - safety_penalty)
    if safety_score < 100:
        reasons.append(
            f"检测到潜在不适合教学场景的敏感词（{', '.join(safety_hits[:3])}），需要人工复核。"
        )

    w = cfg.weights
    weighted = (
        w.get("freshness", 0.25) * freshness_score
        + w.get("interest", 0.20) * interest_score
        + w.get("teachability", 0.25) * teachability_score
        + w.get("info_density", 0.15) * info_density_score
        + w.get("exercise_potential", 0.15) * exercise_potential_score
    )
    total_score = round(weighted * (safety_score / 100.0), 2)

    return ArticleScore(
        freshness_score=round(freshness_score, 2),
        interest_score=round(interest_score, 2),
        teachability_score=round(min(100.0, teachability_score), 2),
        info_density_score=round(info_density_score, 2),
        exercise_potential_score=round(exercise_potential_score, 2),
        safety_score=round(safety_score, 2),
        total_score=total_score,
        reasons=reasons,
    )


def _score_freshness(article: RawArticle) -> float:
    if article.published_at is None:
        return 70.0

    age = utc_now() - article.published_at
    if age <= timedelta(hours=24):
        return 100.0
    if age <= timedelta(hours=48):
        return 90.0
    if age <= timedelta(hours=72):
        return 80.0
    if age <= timedelta(days=7):
        return 65.0
    return 45.0

