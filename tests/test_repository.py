from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from teacher_content_reminder.models import (
    ArticleCandidate,
    ArticleScore,
    ExerciseQuestion,
    GeneratedContentPackage,
    GeneratedPreviewItem,
    PreviewItem,
    RawArticle,
)
from teacher_content_reminder.repository import SQLiteRepository
from teacher_content_reminder.utils import utc_now


def _build_preview_item() -> GeneratedPreviewItem:
    article = RawArticle(
        source_name="nasa_news",
        source_category="science_nature",
        source_url="https://example.com/story",
        canonical_url="https://example.com/story",
        title="Example Space Story",
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
        total_score=96.0,
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
        optimized_title="Example Space Story for Class",
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
            )
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
            )
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


class RepositoryTests(unittest.TestCase):
    def test_review_queue_and_delivery_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = SQLiteRepository(Path(tmp_dir) / "test.sqlite3")
            repo.initialize()
            generated = _build_preview_item()
            repo.save_article(generated.preview.article, generated.preview.score)
            package_id = repo.save_generated_package(generated.preview.article, generated.package)
            generated.package.package_id = package_id

            queue_id = repo.enqueue_review_item(generated, recommendation="special", status="pending_review")
            queued = repo.get_review_queue_item(queue_id)
            self.assertIsNotNone(queued)
            self.assertEqual(queued.review_recommendation, "special")
            self.assertEqual(queued.status, "pending_review")

            repo.update_review_status(
                queue_id,
                "approved",
                reviewer_note="Looks strong for beta.",
                export_directory="/tmp/export",
            )
            approved = repo.get_review_queue_item(queue_id)
            self.assertIsNotNone(approved)
            self.assertEqual(approved.status, "approved")
            self.assertEqual(approved.reviewer_note, "Looks strong for beta.")
            self.assertEqual(approved.export_directory, "/tmp/export")

            event_id = repo.record_delivery_event(
                channel="dingtalk",
                status="sent",
                response_payload={"errcode": 0, "errmsg": "ok"},
                queue_id=queue_id,
                package_id=package_id,
            )
            self.assertGreater(event_id, 0)
            today = utc_now().astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
            self.assertEqual(
                repo.count_delivery_events_for_date("dingtalk", today, timezone_name="Asia/Shanghai"),
                1,
            )

            last_event = repo.get_last_delivery_event("dingtalk", status="sent")
            self.assertIsNotNone(last_event)
            self.assertEqual(last_event.queue_id, queue_id)

            preview = repo.load_generated_preview_by_queue_id(queue_id)
            self.assertEqual(preview.package.package_id, package_id)
            self.assertEqual(preview.package.optimized_title, "Example Space Story for Class")

            log_id = repo.record_activity_log(
                event_type="scheduled_run",
                status="completed",
                message="Scheduled run queued 1 item(s), dispatched 0.",
                source_name="nasa_news",
                queue_id=queue_id,
                package_id=package_id,
                payload={"queued_count": 1, "dispatch_reason": "outside_send_window"},
            )
            self.assertGreater(log_id, 0)

            logs = repo.list_activity_logs(limit=5)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].event_type, "scheduled_run")
            self.assertEqual(logs[0].payload["queued_count"], 1)

            status_counts = repo.count_review_queue_by_status()
            recommendation_counts = repo.count_review_queue_by_recommendation()
            self.assertEqual(status_counts["approved"], 1)
            self.assertEqual(recommendation_counts["special"], 1)

    def test_content_hash_dedup(self) -> None:
        """has_article should detect duplicate content even under a different URL."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            from teacher_content_reminder.utils import hash_text

            repo = SQLiteRepository(Path(tmp_dir) / "test.sqlite3")
            repo.initialize()
            generated = _build_preview_item()
            repo.save_article(generated.preview.article, generated.preview.score)

            # Same content, different URL — should be detected as duplicate
            content_hash = hash_text(generated.preview.article.raw_text)
            self.assertTrue(repo.has_article("https://other-url.com/different", content_hash=content_hash))

            # Different content hash — should not be detected as duplicate
            self.assertFalse(repo.has_article("https://other-url.com/different", content_hash="deadbeef"))

    def test_has_article_by_canonical_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = SQLiteRepository(Path(tmp_dir) / "test.sqlite3")
            repo.initialize()
            generated = _build_preview_item()
            repo.save_article(generated.preview.article, generated.preview.score)
            self.assertTrue(repo.has_article(generated.preview.article.canonical_url))
            self.assertFalse(repo.has_article("https://totally-unknown.com/article"))


if __name__ == "__main__":
    unittest.main()
