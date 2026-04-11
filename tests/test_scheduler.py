from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from teacher_content_reminder.config import load_config
from teacher_content_reminder.models import (
    ArticleCandidate,
    ArticleScore,
    DeliveryEvent,
    ExerciseQuestion,
    GeneratedContentPackage,
    GeneratedPreviewItem,
    PreviewItem,
    RawArticle,
)
from teacher_content_reminder.scheduler import (
    cron_matches,
    dispatch_decision,
    due_source_names,
    initial_queue_status,
    review_recommendation,
)
from teacher_content_reminder.utils import utc_now


def _build_preview_item(title: str, recommendation_score: float) -> GeneratedPreviewItem:
    article = RawArticle(
        source_name="nasa_news",
        source_category="science_nature",
        source_url=f"https://example.com/{title.lower().replace(' ', '-')}",
        canonical_url=f"https://example.com/{title.lower().replace(' ', '-')}",
        title=title,
        author="Example Author",
        published_at=utc_now() - timedelta(hours=4),
        excerpt="A short excerpt about a space mission and why it matters in class.",
        lead_image_url="https://example.com/image.jpg",
        raw_html="<html></html>",
        raw_text="NASA shared a new story about science on the ISS. " * 40,
        word_count=320,
        fetched_at=utc_now(),
    )
    score = ArticleScore(
        freshness_score=18.0,
        interest_score=18.0,
        teachability_score=17.0,
        info_density_score=16.0,
        exercise_potential_score=17.0,
        safety_score=10.0,
        total_score=recommendation_score,
        reasons=["fresh", "teachable"],
    )
    preview = PreviewItem(
        candidate=ArticleCandidate(
            source_name=article.source_name,
            source_category=article.source_category,
            url=article.source_url,
            title=article.title,
            summary=article.excerpt,
            published_at=article.published_at,
        ),
        article=article,
        score=score,
    )
    package = GeneratedContentPackage(
        audience="senior",
        exercise_profile="default",
        optimized_title=title,
        summary="A classroom-friendly summary.",
        teaching_value="Useful for cause-and-effect and science vocabulary.",
        reading_passage="Students read about a science mission and discuss why it matters. " * 20,
        keywords=["science", "mission", "station"],
        discussion_points=["Why is this mission important?"],
        reading_questions=[
            ExerciseQuestion(
                question_id="reading-1",
                question_type="multiple_choice",
                stem="What is the article mainly about?",
                options=["A mission", "A game", "A sport", "A movie"],
                answer="A mission",
                explanation="The passage focuses on the mission.",
            ),
            ExerciseQuestion(
                question_id="reading-2",
                question_type="multiple_choice",
                stem="Where does the science happen?",
                options=["On the station", "In a park", "At home", "In a shop"],
                answer="On the station",
                explanation="The passage mentions the station.",
            ),
            ExerciseQuestion(
                question_id="reading-3",
                question_type="multiple_choice",
                stem="Why can teachers use this story?",
                options=["For discussion", "For shopping", "For cooking", "For games"],
                answer="For discussion",
                explanation="The passage is suitable for class discussion.",
            ),
        ],
        cloze_passage="The mission brought new science tools to the station.",
        cloze_questions=[
            ExerciseQuestion(
                question_id="cloze-1",
                question_type="cloze",
                stem="Blank 1",
                options=["mission", "game", "story", "class"],
                answer="mission",
                explanation="Mission best fits the context.",
            ),
            ExerciseQuestion(
                question_id="cloze-2",
                question_type="cloze",
                stem="Blank 2",
                options=["science", "song", "holiday", "traffic"],
                answer="science",
                explanation="Science fits the topic.",
            ),
            ExerciseQuestion(
                question_id="cloze-3",
                question_type="cloze",
                stem="Blank 3",
                options=["station", "kitchen", "garden", "museum"],
                answer="station",
                explanation="Station matches the passage.",
            ),
        ],
        traceability_notes=["Based on the original article title and excerpt."],
        task_timings={"extract_facts": 0.1},
        task_providers={"extract_facts": "mock"},
        task_models={"extract_facts": "mock-teacher-v1"},
        generator_provider="mock",
        generator_model="mock-teacher-v1",
        generated_at=utc_now(),
    )
    return GeneratedPreviewItem(preview=preview, package=package)


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config("config/default.toml")

    def test_due_source_names_match_cron(self) -> None:
        nasa_time = datetime(2026, 4, 13, 8, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        ap_time = datetime(2026, 4, 13, 8, 10, tzinfo=ZoneInfo("Asia/Shanghai"))
        science_time = datetime(2026, 4, 13, 8, 15, tzinfo=ZoneInfo("Asia/Shanghai"))
        smithsonian_time = datetime(2026, 4, 13, 8, 25, tzinfo=ZoneInfo("Asia/Shanghai"))

        self.assertIn("nasa_news", due_source_names(self.config, current=nasa_time))
        self.assertIn("ap_highlights", due_source_names(self.config, current=ap_time))
        self.assertIn("science_news", due_source_names(self.config, current=science_time))
        self.assertIn("smithsonian_science", due_source_names(self.config, current=smithsonian_time))
        self.assertTrue(cron_matches("0,30 * * * *", nasa_time))

    def test_review_thresholds_follow_beta_strategy(self) -> None:
        self.assertEqual(review_recommendation(self.config, 74.9), "discard")
        self.assertEqual(review_recommendation(self.config, 80.0), "review")
        self.assertEqual(review_recommendation(self.config, 85.0), "auto_send")
        self.assertEqual(review_recommendation(self.config, 91.0), "special")
        self.assertEqual(initial_queue_status(self.config, "review"), "pending_review")

    def test_dispatch_requires_send_window_and_gap(self) -> None:
        morning = datetime(2026, 4, 13, 7, 35, tzinfo=ZoneInfo("Asia/Shanghai"))
        allowed = dispatch_decision(self.config, now=morning, sent_today_count=0, last_event=None)
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.slot, "morning")

        midday = datetime(2026, 4, 13, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        blocked = dispatch_decision(self.config, now=midday, sent_today_count=0, last_event=None)
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.reason, "outside_send_window")

        recent_event = DeliveryEvent(
            event_id=1,
            queue_id=1,
            package_id=1,
            channel="dingtalk",
            status="sent",
            created_at=morning - timedelta(hours=1),
        )
        gap_blocked = dispatch_decision(self.config, now=morning, sent_today_count=1, last_event=recent_event)
        self.assertFalse(gap_blocked.allowed)
        self.assertEqual(gap_blocked.reason, "minimum_gap_not_reached")

    def test_evening_auto_dispatch_requires_special_items(self) -> None:
        try:
            from teacher_content_reminder.pipeline import ContentPipeline
        except Exception as exc:  # pragma: no cover - optional dependency guard
            self.skipTest(f"Pipeline dependencies unavailable: {exc}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            pipeline = ContentPipeline(config_path="config/default.toml", db_path=Path(tmp_dir) / "test.sqlite3")
            pipeline.initialize()

            generated = _build_preview_item("Regular Evening Candidate", 85.0)
            pipeline.repository.save_article(generated.preview.article, generated.preview.score)
            package_id = pipeline.repository.save_generated_package(generated.preview.article, generated.package)
            generated.package.package_id = package_id
            pipeline.repository.enqueue_review_item(generated, recommendation="auto_send", status="approved")

            evening = datetime(2026, 4, 13, 20, 35, tzinfo=ZoneInfo("Asia/Shanghai"))
            result = pipeline.dispatch_approved_items(now=evening, send=False, force=False, max_items=1)

            self.assertFalse(result["decision"]["allowed"])
            self.assertEqual(result["decision"]["reason"], "no_evening_special_items")

            special_generated = _build_preview_item("Special Evening Candidate", 93.0)
            pipeline.repository.save_article(special_generated.preview.article, special_generated.preview.score)
            special_package_id = pipeline.repository.save_generated_package(
                special_generated.preview.article,
                special_generated.package,
            )
            special_generated.package.package_id = special_package_id
            queue_id = pipeline.repository.enqueue_review_item(
                special_generated,
                recommendation="special",
                status="approved",
            )
            special_item = pipeline.repository.get_review_queue_item(queue_id)
            self.assertIsNotNone(special_item)

            allowed_result = pipeline.dispatch_approved_items(now=evening, send=False, force=False, max_items=1)
            self.assertTrue(allowed_result["decision"]["allowed"])
            self.assertEqual(len(allowed_result["items"]), 1)


if __name__ == "__main__":
    unittest.main()
