from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from teacher_content_reminder.config import load_config
from teacher_content_reminder.exporters import ExportService, render_print_html, render_print_markdown
from teacher_content_reminder.generation import GenerationService
from teacher_content_reminder.llm.mock import MockLLMClient
from teacher_content_reminder.models import ArticleCandidate, GeneratedPreviewItem, PreviewItem, RawArticle
from teacher_content_reminder.scoring import score_article
from teacher_content_reminder.utils import utc_now


class ExporterTests(unittest.TestCase):
    def test_render_print_formats_include_extension_section(self) -> None:
        item = _build_generated_item()
        _, markdown = render_print_markdown(item, variant="teacher")
        _, html = render_print_html(item, variant="teacher")
        self.assertIn("Extension Activities", markdown)
        self.assertIn("Answer Key", markdown)
        self.assertIn("Extension Activities", html)
        self.assertIn("Answer Key", html)

    def test_student_render_omits_answer_key(self) -> None:
        item = _build_generated_item()
        _, markdown = render_print_markdown(item, variant="student")
        _, html = render_print_html(item, variant="student")
        self.assertIn("Before You Read", markdown)
        self.assertNotIn("Answer Key", markdown)
        self.assertIn("Before You Read", html)
        self.assertNotIn("Discussion Points", html)

    def test_export_service_writes_files(self) -> None:
        item = _build_generated_item()
        with TemporaryDirectory() as temp_dir:
            service = ExportService(temp_dir)
            result = service.export_generated_preview(item, formats=("markdown", "html", "json"))

            export_dir = Path(result["directory"])
            self.assertTrue((export_dir / "worksheet.md").exists())
            self.assertTrue((export_dir / "worksheet.html").exists())
            self.assertTrue((export_dir / "teacher_worksheet.md").exists())
            self.assertTrue((export_dir / "teacher_worksheet.html").exists())
            self.assertTrue((export_dir / "student_worksheet.md").exists())
            self.assertTrue((export_dir / "student_worksheet.html").exists())
            self.assertTrue((export_dir / "package.json").exists())


def _build_generated_item() -> GeneratedPreviewItem:
    config = load_config("config/default.toml")
    generation = GenerationService(config, client=MockLLMClient())
    article = RawArticle(
        source_name="nasa_news",
        source_category="science_nature",
        source_url="https://example.com/story",
        canonical_url="https://example.com/story",
        title="NASA Mission Inspires a New Reading Task",
        excerpt="A short science update becomes a classroom reading.",
        lead_image_url="https://example.com/image.jpg",
        raw_html="<html></html>",
        raw_text=(
            "NASA released a mission update in 2026 that included crew details, science goals, and engineering lessons. "
            "Teachers can use the story to discuss evidence, teamwork, and future exploration. "
            "Students can identify the main idea, support it with details, and explain why the mission matters."
        ),
        word_count=58,
        fetched_at=utc_now(),
        published_at=utc_now() - timedelta(hours=2),
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
        score=score_article(article),
    )
    package = generation.generate(article, audience_key="senior", exercise_profile_name="default")
    return GeneratedPreviewItem(preview=preview, package=package)


if __name__ == "__main__":
    unittest.main()
