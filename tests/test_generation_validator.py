from datetime import datetime, timezone
import unittest

from teacher_content_reminder.generation.validator import (
    _string_list,
    ensure_package_quality,
    parse_cloze_payload,
    parse_question_list,
    parse_title_summary,
)
from teacher_content_reminder.models import ExerciseQuestion, GeneratedContentPackage


class GenerationValidatorTests(unittest.TestCase):
    def test_string_list_accepts_multiline_bullets(self) -> None:
        value = "- first item\n- second item\n- third item"
        result = _string_list(value, minimum=3)
        self.assertEqual(result, ["first item", "second item", "third item"])

    def test_parse_question_list_rejects_meta_distractors(self) -> None:
        payload = {
            "questions": [
                {
                    "stem": "What is the main idea of the passage?",
                    "options": [
                        "A. The passage directly answers this question.",
                        "B. The report says the event had no wider importance.",
                        "C. It describes a successful moon mission.",
                        "D. It is a fictional story.",
                    ],
                    "answer": "C",
                },
                {
                    "stem": "Which detail is mentioned?",
                    "options": [
                        "A. A crew returned safely to Earth.",
                        "B. The passage directly answers this question.",
                        "C. The report claims there is no evidence or detail.",
                        "D. The mission never launched.",
                    ],
                    "answer": "A",
                },
            ]
        }
        with self.assertRaisesRegex(ValueError, "meta distractors"):
            parse_question_list(payload, minimum=2, prefix="reading")

    def test_parse_cloze_payload_rejects_long_sentence_options(self) -> None:
        payload = {
            "cloze_passage": "NASA tested (1) carefully before the (2) returned to (3) after the long (4).",
            "questions": [
                {
                    "stem": "What is the spacecraft name?",
                    "options": [
                        "A. The passage directly answers this question about the spacecraft name.",
                        "B. Orion",
                        "C. idea",
                        "D. future",
                    ],
                    "answer": "B",
                },
                {
                    "stem": "Choose the best answer for blank (2).",
                    "options": [
                        "A. crew",
                        "B. team",
                        "C. group",
                        "D. The report says the event had no wider importance.",
                    ],
                    "answer": "A",
                },
                {
                    "stem": "Choose the best answer for blank (3).",
                    "options": [
                        "A. return",
                        "B. arrive",
                        "C. landing",
                        "D. orbit",
                    ],
                    "answer": "D",
                },
                {
                    "stem": "Choose the best answer for blank (4).",
                    "options": [
                        "A. Earth",
                        "B. Moon",
                        "C. space",
                        "D. Mars",
                    ],
                    "answer": "A",
                },
            ],
        }
        with self.assertRaisesRegex(ValueError, "too long"):
            parse_cloze_payload(payload, minimum=4)

    def test_parse_title_summary_warns_on_unsupported_year(self) -> None:
        payload = {
            "optimized_title": "Artemis II Returns",
            "summary": "The spacecraft splashed down in 2024 after a successful mission.",
            "teaching_value": "Useful for STEM discussion.",
            "traceability_notes": ["NASA source", "Mission report"],
        }
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            parse_title_summary(payload, source_text="Artemis II splashed down in 2026 after a successful mission.")
            year_warnings = [x for x in w if "year" in str(x.message).lower()]
            self.assertGreater(len(year_warnings), 0, "Expected a year warning")

    def test_ensure_package_quality_allows_small_word_underflow(self) -> None:
        question = ExerciseQuestion(
            question_id="q1",
            question_type="reading",
            stem="What is the main idea?",
            options=["A. one", "B. two", "C. three", "D. four"],
            answer="A",
            explanation="Because the passage says so.",
        )
        package = GeneratedContentPackage(
            audience="senior",
            exercise_profile="default",
            optimized_title="Sample",
            summary="Summary",
            teaching_value="Teaching value",
            reading_passage="word " * 248,
            keywords=["science", "space", "crew"],
            discussion_points=["Discuss the article."],
            reading_questions=[question] * 5,
            cloze_passage="(1) " * 4,
            cloze_questions=[question] * 4,
            traceability_notes=["Source fact one", "Source fact two"],
            task_timings={},
            task_providers={},
            task_models={},
            generator_provider="qwen",
            generator_model="qwen-plus",
            generated_at=datetime.now(timezone.utc),
        )
        result = ensure_package_quality(package, min_words=250, max_words=450, min_questions=5, min_cloze_questions=4)
        self.assertEqual(result.optimized_title, "Sample")


if __name__ == "__main__":
    unittest.main()
