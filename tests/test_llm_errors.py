import unittest

from teacher_content_reminder.llm.errors import classify_http_error, classify_network_error


class LLMErrorTests(unittest.TestCase):
    def test_auth_error_is_not_retryable(self) -> None:
        error = classify_http_error("qwen", 401, "invalid api key")
        self.assertFalse(error.retryable)
        self.assertEqual(error.kind, "auth")

    def test_billing_error_is_not_retryable(self) -> None:
        error = classify_http_error("deepseek", 402, "Insufficient Balance")
        self.assertFalse(error.retryable)
        self.assertEqual(error.kind, "billing")

    def test_rate_limit_error_is_retryable(self) -> None:
        error = classify_http_error("kimi", 429, "too many requests")
        self.assertTrue(error.retryable)
        self.assertEqual(error.kind, "rate_limit")

    def test_network_timeout_is_retryable(self) -> None:
        error = classify_network_error("deepseek", "timed out")
        self.assertTrue(error.retryable)


if __name__ == "__main__":
    unittest.main()
