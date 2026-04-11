import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from teacher_content_reminder.delivery.dingtalk import DingTalkBotClient


class DingTalkClientTests(unittest.TestCase):
    def test_signed_url_adds_single_encoded_signature(self) -> None:
        client = DingTalkBotClient(
            webhook_url="https://example.com/robot/send?access_token=test-token",
            secret="SEC-test-secret",
        )
        with patch("teacher_content_reminder.delivery.dingtalk.time.time", return_value=1710000000.0):
            signed_url = client._signed_url()

        parsed = urlparse(signed_url)
        query = parse_qs(parsed.query)
        self.assertEqual(query["access_token"][0], "test-token")
        self.assertEqual(query["timestamp"][0], "1710000000000")
        self.assertIn("sign", query)
        self.assertNotIn("%2B", query["sign"][0])
        self.assertNotIn("%25", parsed.query)


if __name__ == "__main__":
    unittest.main()
