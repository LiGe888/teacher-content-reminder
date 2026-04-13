from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
from teacher_content_reminder.utils import utc_now


def _build_generated_preview(title: str, score_total: float) -> GeneratedPreviewItem:
    article = RawArticle(
        source_name="nasa_news",
        source_category="science_nature",
        source_url=f"https://example.com/{title.lower().replace(' ', '-')}",
        canonical_url=f"https://example.com/{title.lower().replace(' ', '-')}",
        title=title,
        author="Example Author",
        published_at=utc_now() - timedelta(hours=3),
        excerpt="A short excerpt for testing.",
        lead_image_url="https://example.com/image.jpg",
        raw_html="<html></html>",
        raw_text="Example text " * 50,
        word_count=100,
        fetched_at=utc_now(),
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
        score=ArticleScore(
            freshness_score=10.0,
            interest_score=10.0,
            teachability_score=10.0,
            info_density_score=10.0,
            exercise_potential_score=10.0,
            safety_score=10.0,
            total_score=score_total,
            reasons=["test"],
        ),
    )
    package = GeneratedContentPackage(
        audience="senior",
        exercise_profile="default",
        optimized_title=title,
        summary="summary",
        teaching_value="value",
        reading_passage="reading passage",
        keywords=["k1"],
        discussion_points=["d1"],
        reading_questions=[
            ExerciseQuestion(
                question_id="q1",
                question_type="multiple_choice",
                stem="stem",
                options=["a", "b", "c", "d"],
                answer="a",
                explanation="exp",
            )
        ],
        cloze_passage="cloze passage",
        cloze_questions=[
            ExerciseQuestion(
                question_id="cq1",
                question_type="cloze",
                stem="stem",
                options=["a", "b", "c", "d"],
                answer="a",
                explanation="exp",
            )
        ],
        traceability_notes=["n1"],
        task_timings={"extract_facts": 0.1},
        task_providers={"extract_facts": "mock"},
        task_models={"extract_facts": "mock-model"},
        generator_provider="mock",
        generator_model="mock-model",
        generated_at=utc_now(),
        package_id=None,
    )
    return GeneratedPreviewItem(preview=preview, package=package)


class PipelineQueueTests(unittest.TestCase):
    def test_low_score_item_is_not_queued_and_logs_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.sqlite3"
            pipeline = ContentPipeline(config_path="config/default.toml", db_path=db_path)
            pipeline.initialize()

            generated = _build_generated_preview("Low Score Story", 60.0)
            with patch.object(pipeline, "generate_preview_source", return_value=[generated]):
                queued = pipeline.queue_source_for_review("nasa_news", limit=1)

            self.assertEqual(queued, [])
            self.assertEqual(pipeline.repository.count_review_queue_by_status(), {})

            logs = pipeline.repository.list_activity_logs(event_type="queue_item", status="skipped", limit=10)
            self.assertTrue(logs)
            latest = logs[0]
            self.assertEqual(latest.source_name, "nasa_news")
            self.assertEqual(latest.payload.get("reason"), "low_score")
            self.assertEqual(latest.payload.get("score_total"), 60.0)

