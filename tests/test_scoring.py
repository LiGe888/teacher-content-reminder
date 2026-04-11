from datetime import timedelta
import unittest

from teacher_content_reminder.models import RawArticle
from teacher_content_reminder.scoring import score_article
from teacher_content_reminder.utils import utc_now


class ScoringTests(unittest.TestCase):
    def test_recent_science_article_scores_well(self) -> None:
        article = RawArticle(
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

        score = score_article(article)
        self.assertGreaterEqual(score.total_score, 75.0)
        self.assertGreaterEqual(score.freshness_score, 90.0)


if __name__ == "__main__":
    unittest.main()

