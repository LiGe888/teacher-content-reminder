import os
import unittest
from unittest.mock import patch

from teacher_content_reminder.config import load_config
from teacher_content_reminder.diagnostics import build_beta_report, build_runtime_report


class DiagnosticsTests(unittest.TestCase):
    def test_report_shows_missing_items_when_env_absent(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DINGTALK_WEBHOOK_URL": "",
                "DINGTALK_SECRET": "",
                "DINGTALK_ALERT_WEBHOOK_URL": "",
                "DINGTALK_ALERT_SECRET": "",
            },
            clear=False,
        ):
            config = load_config("config/default.toml")
            report = build_runtime_report(config)
        self.assertIn("providers", report)
        self.assertIn("missing_items", report)
        self.assertTrue(any("DINGTALK_WEBHOOK_URL" in item for item in report["missing_items"]))
        self.assertTrue(any("DINGTALK_SECRET" in item for item in report["missing_items"]))
        self.assertTrue(any("DINGTALK_ALERT_WEBHOOK_URL" in item for item in report["missing_items"]))
        self.assertTrue(any("DINGTALK_ALERT_SECRET" in item for item in report["missing_items"]))
        self.assertIn("alerting", report)

    def test_beta_report_shows_router_chain(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DINGTALK_WEBHOOK_URL": "",
                "DINGTALK_SECRET": "",
                "DINGTALK_ALERT_WEBHOOK_URL": "",
                "DINGTALK_ALERT_SECRET": "",
            },
            clear=False,
        ):
            config = load_config("config/default.toml")
            report = build_beta_report(config, live=False)
        self.assertEqual(report["router_chain"][0]["name"], "qwen")
        self.assertTrue(report["ready_generation"])
        self.assertFalse(report["ready_delivery"])
        self.assertFalse(report["ready_alerting"])


if __name__ == "__main__":
    unittest.main()
