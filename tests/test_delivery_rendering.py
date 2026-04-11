from datetime import timedelta
import unittest

from teacher_content_reminder.delivery import render_dingtalk_markdown
from teacher_content_reminder.generation import GenerationService
from teacher_content_reminder.config import load_config
from teacher_content_reminder.llm.mock import MockLLMClient
from teacher_content_reminder.models import ArticleCandidate, ArticleScore, PreviewItem, RawArticle, GeneratedPreviewItem
from teacher_content_reminder.scoring import score_article
from teacher_content_reminder.utils import utc_now


class DeliveryRenderingTests(unittest.TestCase):
    def test_render_markdown_contains_core_sections(self) -> None:
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
                "NASA released a mission update that included crew details, science goals, and engineering lessons. "
                "Teachers can use the story to discuss evidence, teamwork, and future exploration.\n\n"
                "Students can identify the main idea, support it with details, and explain why the mission matters."
            ),
            word_count=60,
            fetched_at=utc_now(),
            published_at=utc_now() - timedelta(hours=2),
        )
        score = score_article(article)
        preview = PreviewItem(
            candidate=ArticleCandidate(
                source_name="nasa_news",
                source_category="science_nature",
                url=article.source_url,
                title=article.title,
                summary=article.excerpt,
                published_at=article.published_at,
            ),
            article=article,
            score=score,
        )
        package = generation.generate(article, audience_key="senior", exercise_profile_name="default")
        title, markdown = render_dingtalk_markdown(GeneratedPreviewItem(preview=preview, package=package))

        self.assertIn("Summary", markdown)
        self.assertIn("Reading Questions", markdown)
        self.assertIn("Open original article", markdown)
        self.assertEqual(title, package.optimized_title)


if __name__ == "__main__":
    unittest.main()
