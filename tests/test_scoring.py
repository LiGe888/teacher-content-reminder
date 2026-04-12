from datetime import timedelta
import unittest

from teacher_content_reminder.models import RawArticle
from teacher_content_reminder.scoring import ScoringConfig, score_article
from teacher_content_reminder.utils import utc_now


def _make_article(**kwargs) -> RawArticle:
    defaults = dict(
        source_name="nasa_news",
        source_category="science_nature",
        source_url="https://example.com/story",
        canonical_url="https://example.com/story",
        title="NASA shares new images from a surprising moon mission",
        excerpt="A fresh mission update offers classroom-friendly material.",
        lead_image_url="https://example.com/image.jpg",
        raw_html="<html></html>",
        raw_text=(
            "NASA released new moon images after the mission entered orbit.\n\n"
            "Scientists explained why the heat shield matters.\n\n"
            "The update included mission timing, crew details, and future plans.\n\n"
            "Teachers can use the timeline to discuss cause and effect."
        ),
        word_count=180,
        fetched_at=utc_now(),
        published_at=utc_now() - timedelta(hours=6),
    )
    defaults.update(kwargs)
    return RawArticle(**defaults)


class ScoringTests(unittest.TestCase):
    def test_recent_science_article_scores_well(self) -> None:
        article = _make_article()
        score = score_article(article)
        self.assertGreaterEqual(score.total_score, 75.0)
        self.assertGreaterEqual(score.freshness_score, 90.0)

    # --- freshness boundary tests ---

    def test_freshness_very_recent(self) -> None:
        article = _make_article(published_at=utc_now() - timedelta(hours=1))
        score = score_article(article)
        self.assertEqual(score.freshness_score, 100.0)

    def test_freshness_24_to_48h(self) -> None:
        article = _make_article(published_at=utc_now() - timedelta(hours=36))
        score = score_article(article)
        self.assertEqual(score.freshness_score, 90.0)

    def test_freshness_48_to_72h(self) -> None:
        article = _make_article(published_at=utc_now() - timedelta(hours=60))
        score = score_article(article)
        self.assertEqual(score.freshness_score, 80.0)

    def test_freshness_old_article(self) -> None:
        article = _make_article(published_at=utc_now() - timedelta(days=10))
        score = score_article(article)
        self.assertEqual(score.freshness_score, 45.0)

    def test_freshness_unknown_date(self) -> None:
        article = _make_article(published_at=None)
        score = score_article(article)
        self.assertEqual(score.freshness_score, 70.0)

    # --- safety blocklist tests ---

    def test_safety_penalty_applied_for_blocked_word(self) -> None:
        article = _make_article(
            raw_text="This article contains graphic violence and disturbing content.\n\n" * 5,
            word_count=60,
        )
        score = score_article(article)
        self.assertLess(score.safety_score, 100.0)
        self.assertLess(score.total_score, score.freshness_score)  # penalty reduces total

    def test_safety_score_zero_for_multiple_hits(self) -> None:
        article = _make_article(
            raw_text="graphic beheaded massacre porn lottery celebrity scandal " * 5,
            word_count=40,
        )
        score = score_article(article)
        self.assertEqual(score.safety_score, 0.0)
        self.assertEqual(score.total_score, 0.0)

    def test_clean_article_has_full_safety_score(self) -> None:
        article = _make_article()
        score = score_article(article)
        self.assertEqual(score.safety_score, 100.0)

    # --- teachability word count boundaries ---

    def test_teachability_optimal_word_count(self) -> None:
        article = _make_article(word_count=400)
        score = score_article(article)
        self.assertGreaterEqual(score.teachability_score, 80.0)

    def test_teachability_too_short(self) -> None:
        article = _make_article(word_count=50, excerpt="", lead_image_url="")
        score = score_article(article)
        self.assertLessEqual(score.teachability_score, 50.0)

    # --- custom ScoringConfig ---

    def test_custom_scoring_config_keywords(self) -> None:
        cfg = ScoringConfig(
            interest_keywords={"science_nature": ("moon", "orbit")},
        )
        article = _make_article(title="Moon orbit discovery", raw_text="The moon orbit was studied. " * 20)
        score = score_article(article, scoring_config=cfg)
        self.assertGreater(score.interest_score, 55.0)

    def test_custom_scoring_config_weights(self) -> None:
        # Heavily weight freshness
        cfg = ScoringConfig(weights={"freshness": 0.8, "interest": 0.05, "teachability": 0.05, "info_density": 0.05, "exercise_potential": 0.05})
        article = _make_article(published_at=utc_now() - timedelta(hours=1))
        score = score_article(article, scoring_config=cfg)
        # With 80% weight on freshness=100, total should be high
        self.assertGreater(score.total_score, 70.0)

    def test_custom_blocklist(self) -> None:
        cfg = ScoringConfig(safety_blocklist=("forbidden_word",))
        article = _make_article(raw_text="This article mentions forbidden_word in context. " * 5)
        score = score_article(article, scoring_config=cfg)
        self.assertLess(score.safety_score, 100.0)

    # --- reasons list ---

    def test_reasons_populated(self) -> None:
        article = _make_article()
        score = score_article(article)
        self.assertGreater(len(score.reasons), 0)

    def test_safety_reason_included_when_blocked(self) -> None:
        article = _make_article(raw_text="graphic content here " * 10)
        score = score_article(article)
        self.assertTrue(any("敏感词" in r for r in score.reasons))


if __name__ == "__main__":
    unittest.main()

