from datetime import timedelta
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from teacher_content_reminder.models import (
    ActivityLogEntry,
    ArticleCandidate,
    ArticleScore,
    ExerciseQuestion,
    GeneratedContentPackage,
    GeneratedPreviewItem,
    PreviewItem,
    RawArticle,
    ReviewQueueItem,
)
from teacher_content_reminder.review_dashboard import (
    activity_log_payload,
    generated_preview_payload,
    render_review_dashboard,
    review_queue_payload,
)
from teacher_content_reminder.utils import utc_now


def _build_generated_preview() -> GeneratedPreviewItem:
    article = RawArticle(
        source_name="nasa_news",
        source_category="science_nature",
        source_url="https://example.com/story",
        canonical_url="https://example.com/story",
        title="Space Science for Class",
        author="Example Author",
        published_at=utc_now() - timedelta(hours=3),
        excerpt="A short summary for teachers.",
        lead_image_url="https://example.com/cover.jpg",
        raw_html="<html></html>",
        raw_text="A long article about science and classroom discussion." * 30,
        word_count=280,
        fetched_at=utc_now(),
    )
    score = ArticleScore(
        freshness_score=16.0,
        interest_score=17.0,
        teachability_score=18.0,
        info_density_score=15.0,
        exercise_potential_score=17.0,
        safety_score=10.0,
        total_score=93.0,
        reasons=["fresh", "safe"],
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
        optimized_title="Space Science for Class",
        summary="A classroom summary.",
        teaching_value="Useful for vocabulary and science discussion.",
        reading_passage="Students read about science in orbit." * 30,
        keywords=["science", "orbit"],
        discussion_points=["Why does space research matter?"],
        reading_questions=[
            ExerciseQuestion(
                question_id="reading-1",
                question_type="multiple_choice",
                stem="What is the main idea?",
                options=["science", "sports", "music", "travel"],
                answer="science",
                explanation="The passage focuses on science.",
            )
        ],
        cloze_passage="Science helps students connect knowledge and life.",
        cloze_questions=[
            ExerciseQuestion(
                question_id="cloze-1",
                question_type="cloze",
                stem="Blank 1",
                options=["Science", "Music", "Travel", "Weather"],
                answer="Science",
                explanation="Science fits the sentence.",
            )
        ],
        traceability_notes=["Derived from the article title and excerpt."],
        task_timings={"extract_facts": 0.1},
        task_providers={"extract_facts": "mock"},
        task_models={"extract_facts": "mock-teacher-v1"},
        generator_provider="mock",
        generator_model="mock-teacher-v1",
        generated_at=utc_now(),
        package_id=7,
    )
    return GeneratedPreviewItem(preview=preview, package=package)


class ReviewDashboardTests(unittest.TestCase):
    def test_payload_helpers_serialize_preview_and_queue(self) -> None:
        generated = _build_generated_preview()
        exports_root = Path(__file__).resolve().parents[1] / ".exports"
        temp_dir = tempfile.mkdtemp(prefix="review-dashboard-", dir=exports_root)
        export_dir = Path(temp_dir)
        (export_dir / "teacher_worksheet.html").write_text("<html>teacher</html>", encoding="utf-8")
        (export_dir / "student_worksheet.html").write_text("<html>student</html>", encoding="utf-8")
        (export_dir / "package.json").write_text("{}", encoding="utf-8")
        queue_item = ReviewQueueItem(
            queue_id=5,
            package_id=generated.package.package_id or 7,
            article_url=generated.preview.article.canonical_url,
            source_name=generated.preview.article.source_name,
            audience=generated.package.audience,
            exercise_profile=generated.package.exercise_profile,
            optimized_title=generated.package.optimized_title,
            score_total=generated.preview.score.total_score,
            review_recommendation="special",
            status="approved",
            reviewer_note="Strong beta candidate.",
            export_directory=str(export_dir),
            created_at=utc_now(),
            updated_at=utc_now(),
            approved_at=utc_now(),
        )

        generated_payload = generated_preview_payload(generated)
        try:
            with patch.dict(os.environ, {"ALERT_VIEW_HOST": "http://47.98.198.2"}, clear=False):
                queue_payload = review_queue_payload(queue_item, generated=generated)
        finally:
            shutil.rmtree(export_dir, ignore_errors=True)

        self.assertEqual(generated_payload["package"]["optimized_title"], "Space Science for Class")
        self.assertEqual(queue_payload["queue"]["queue_id"], 5)
        self.assertEqual(queue_payload["generated"]["preview"]["article"]["source_name"], "nasa_news")
        self.assertIn("generated_at", generated_payload["package"])
        self.assertIn("teacher_html", queue_payload["export_urls"])
        self.assertIn("/exports/", queue_payload["export_urls"]["teacher_html"])

        activity_entry = ActivityLogEntry(
            log_id=9,
            event_type="dispatch",
            status="dry_run",
            message="dry_run Space Science for Class",
            source_name="nasa_news",
            queue_id=5,
            package_id=7,
            payload={"send": False},
            created_at=utc_now(),
        )
        activity_payload = activity_log_payload(activity_entry)
        self.assertEqual(activity_payload["activity"]["event_type"], "dispatch")
        self.assertEqual(activity_payload["activity"]["queue_id"], 5)

    def test_render_review_dashboard_contains_controls_and_sources(self) -> None:
        html = render_review_dashboard(
            sources=[
                {"name": "nasa_news"},
                {"name": "science_news"},
            ],
            default_source="science_news",
        )

        self.assertIn("Teacher Review Desk", html)
        self.assertIn("queue-source-button", html)
        self.assertIn("/api/review-queue", html)
        self.assertIn("/api/activity-log", html)
        self.assertIn("/api/dashboard-summary", html)
        self.assertIn("science_news", html)
        self.assertIn("provider", html)
        self.assertIn("Run History", html)
        self.assertIn("summary-pending", html)
        self.assertIn("summary-alerts", html)
        self.assertIn("activity-event-filter", html)
        self.assertIn("retry-send-button", html)
        self.assertIn("language-select", html)
        self.assertIn("reviewDeskLanguage", html)


if __name__ == "__main__":
    unittest.main()
