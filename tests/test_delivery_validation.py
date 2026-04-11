import unittest

from teacher_content_reminder.delivery.validation import enforce_markdown_limit, normalize_title


class DeliveryValidationTests(unittest.TestCase):
    def test_title_is_trimmed_when_too_long(self) -> None:
        title = "A" * 140
        normalized = normalize_title(title)
        self.assertLessEqual(len(normalized), 100)
        self.assertTrue(normalized.endswith("..."))

    def test_markdown_is_truncated_when_too_long(self) -> None:
        title, markdown = enforce_markdown_limit("Title", "word " * 4000)
        self.assertEqual(title, "Title")
        self.assertLessEqual(len(markdown), 12012)
        self.assertIn("[truncated]", markdown)


if __name__ == "__main__":
    unittest.main()
