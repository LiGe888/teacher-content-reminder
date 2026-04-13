from datetime import timedelta
import unittest

from teacher_content_reminder.delivery.rendering import (
    render_wechat_template_fields,
    render_wecom_markdown,
)
from teacher_content_reminder.generation import GenerationService
from teacher_content_reminder.config import load_config
from teacher_content_reminder.llm.mock import MockLLMClient
from teacher_content_reminder.models import ArticleCandidate, PreviewItem, RawArticle, GeneratedPreviewItem
from teacher_content_reminder.scoring import score_article
from teacher_content_reminder.utils import utc_now


class DeliveryChannelRenderingTests(unittest.TestCase):
    def test_wecom_and_wechat_rendering(self) -> None:
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
            raw_text="NASA mission update for class use. " * 40,
            word_count=200,
            fetched_at=utc_now(),
            published_at=utc_now() - timedelta(hours=2),
        )
        score = score_article(article)
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
        package = generation.generate(article, audience_key="senior", exercise_profile_name="default")
        item = GeneratedPreviewItem(preview=preview, package=package)

        wecom_markdown = render_wecom_markdown(item)
        fields = render_wechat_template_fields(item)

        self.assertIn(package.optimized_title, wecom_markdown)
        self.assertEqual(fields["source_name"], "nasa_news")
        self.assertEqual(fields["article_url"], "https://example.com/story")
        self.assertTrue(fields["score_text"])


if __name__ == "__main__":
    unittest.main()
