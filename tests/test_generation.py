from datetime import timedelta
import unittest

from teacher_content_reminder.config import load_config
from teacher_content_reminder.generation import GenerationService
from teacher_content_reminder.llm.mock import MockLLMClient
from teacher_content_reminder.models import RawArticle
from teacher_content_reminder.utils import utc_now


class GenerationTests(unittest.TestCase):
    def test_mock_generation_builds_package(self) -> None:
        config = load_config("config/default.toml")
        service = GenerationService(config, client=MockLLMClient())
        article = RawArticle(
            source_name="nasa_news",
            source_category="science_nature",
            source_url="https://example.com/story",
            canonical_url="https://example.com/story",
            title="NASA Scientists Share New Moon Mission Lessons for Future Crews",
            author="Example Author",
            published_at=utc_now() - timedelta(hours=5),
            excerpt="Scientists reported what they learned from a recent moon mission and why the details matter.",
            lead_image_url="https://example.com/image.jpg",
            raw_html="<html></html>",
            raw_text=(
                "NASA scientists shared new lessons after a moon mission returned safely to Earth. "
                "The team explained how the crew collected data, tested equipment, and studied the heat shield.\n\n"
                "Engineers said the mission timeline gave them strong evidence for planning future flights. "
                "They also noted that the photos and measurements could support classroom discussion about science and risk.\n\n"
                "Teachers can use the story to discuss cause and effect, problem solving, and the language of discovery. "
                "Students can compare the results with earlier space missions and predict what may happen next."
            ),
            word_count=95,
            fetched_at=utc_now(),
        )

        package = service.generate(article=article, audience_key="senior", exercise_profile_name="default")

        self.assertEqual(package.generator_provider, "mock")
        self.assertGreaterEqual(len(package.reading_questions), 5)
        self.assertGreaterEqual(len(package.cloze_questions), 4)
        self.assertIn("NASA", package.optimized_title)
        self.assertGreaterEqual(len(package.reading_passage.split()), 250)


if __name__ == "__main__":
    unittest.main()
