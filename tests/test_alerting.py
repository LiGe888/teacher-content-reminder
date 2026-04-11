from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from teacher_content_reminder.alerting import AlertService
from teacher_content_reminder.config import AlertingConfig
from teacher_content_reminder.models import (
    ArticleCandidate,
    ArticleScore,
    ExerciseQuestion,
    GeneratedContentPackage,
    GeneratedPreviewItem,
    PreviewItem,
    RawArticle,
)
from teacher_content_reminder.pipeline import ContentPipeline
from teacher_content_reminder.repository import SQLiteRepository
from teacher_content_reminder.utils import utc_now


def _build_preview_item(title: str = "Example Story") -> GeneratedPreviewItem:
    article = RawArticle(
        source_name="nasa_news",
        source_category="science_nature",
        source_url="https://example.com/story",
        canonical_url="https://example.com/story",
        title=title,
        author="Example Author",
        published_at=utc_now() - timedelta(hours=2),
        excerpt="A short excerpt about classroom science.",
        lead_image_url="https://example.com/image.jpg",
        raw_html="<html></html>",
        raw_text="Science article text. " * 50,
        word_count=300,
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
    question = ExerciseQuestion(
        question_id="reading-1",
        question_type="reading",
        stem="What is the main idea?",
        options=["A. science", "B. music", "C. sport", "D. travel"],
        answer="A",
        explanation="The passage is about science.",
    )
    package = GeneratedContentPackage(
        audience="senior",
        exercise_profile="default",
        optimized_title=title,
        summary="A summary for class.",
        teaching_value="Good for science discussion.",
        reading_passage="Students read a science story for class. " * 25,
        keywords=["science", "class", "research"],
        discussion_points=["Why does research matter?"],
        reading_questions=[question] * 5,
        cloze_passage="The mission (1) new science (2) to the station (3) students could discuss (4) class.",
        cloze_questions=[question] * 4,
        traceability_notes=["Source note one", "Source note two"],
        task_timings={},
        task_providers={},
        task_models={},
        generator_provider="mock",
        generator_model="mock-teacher-v1",
        generated_at=utc_now(),
    )
    return GeneratedPreviewItem(preview=preview, package=package)


class _FakeAlertClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def send_markdown(self, title: str, text: str) -> dict[str, object]:
        self.calls.append((title, text))
        return {"errcode": 0, "errmsg": "ok"}


class _StubAlertService(AlertService):
    def __init__(self, repository: SQLiteRepository) -> None:
        super().__init__(
            config=AlertingConfig(
                enabled=True,
                webhook_env="DINGTALK_ALERT_WEBHOOK_URL",
                secret_env="DINGTALK_ALERT_SECRET",
                min_interval_minutes=30,
            ),
            repository=repository,
            timezone_name="Asia/Shanghai",
        )
        self.client = _FakeAlertClient()

    def _build_client(self, webhook_url: str, secret: str | None):  # type: ignore[override]
        return self.client


class _DispatchFailingPipeline(ContentPipeline):
    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path=db_path)
        self.alert_calls: list[dict[str, object]] = []
        self.alerting = _StubAlertService(self.repository)

    def _build_dingtalk_client(self):  # type: ignore[override]
        raise RuntimeError("simulated dispatch failure")

    def _send_alert(self, **kwargs):  # type: ignore[override]
        self.alert_calls.append(dict(kwargs))
        return super()._send_alert(**kwargs)


class AlertingTests(unittest.TestCase):
    def test_duplicate_alerts_are_suppressed_within_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = SQLiteRepository(Path(tmp_dir) / "test.sqlite3")
            repo.initialize()
            service = _StubAlertService(repo)

            first = service.send_alert(
                category="dispatch_failure",
                severity="critical",
                title="Dispatch failed",
                message="First failure",
                fingerprint="dispatch:123",
                force=False,
            )
            second = service.send_alert(
                category="dispatch_failure",
                severity="critical",
                title="Dispatch failed",
                message="Second failure",
                fingerprint="dispatch:123",
                force=False,
            )

            self.assertEqual(first["status"], "sent")
            self.assertEqual(second["status"], "suppressed")
            logs = repo.list_activity_logs(event_type="alert", limit=10)
            self.assertEqual({log.status for log in logs}, {"sent", "suppressed"})

    def test_dispatch_failure_triggers_alert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pipeline = _DispatchFailingPipeline(db_path=Path(tmp_dir) / "test.sqlite3")
            pipeline.initialize()
            generated = _build_preview_item()
            pipeline.repository.save_article(generated.preview.article, generated.preview.score)
            package_id = pipeline.repository.save_generated_package(generated.preview.article, generated.package)
            generated.package.package_id = package_id
            queue_id = pipeline.repository.enqueue_review_item(
                generated,
                recommendation="special",
                status="approved",
            )

            result = pipeline.dispatch_queue_item(queue_id=queue_id, send=True)

            self.assertEqual(result["delivery_status"], "failed")
            self.assertEqual(len(pipeline.alert_calls), 1)
            self.assertEqual(pipeline.alert_calls[0]["category"], "dispatch_failure")
            alert_logs = pipeline.repository.list_activity_logs(event_type="alert", limit=5)
            self.assertTrue(alert_logs)
            self.assertEqual(alert_logs[0].status, "sent")


if __name__ == "__main__":
    unittest.main()
