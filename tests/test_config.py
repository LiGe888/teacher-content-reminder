from pathlib import Path
import unittest

from teacher_content_reminder.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_default_config(self) -> None:
        config = load_config(Path("config/default.toml"))
        self.assertEqual(config.project.name, "teacher-content-reminder")
        self.assertIn("nasa_news", config.sources)
        self.assertEqual(config.sources["nasa_news"].type, "rss")
        self.assertEqual(len(config.enabled_sources), 4)
        self.assertEqual(config.llm.provider, "router")
        self.assertEqual(config.generation.default_audience, "senior")
        self.assertIn("qwen", config.providers)
        self.assertIn("kimi", config.providers)
        self.assertEqual(config.providers["qwen"].model, "qwen-plus")
        self.assertTrue(config.providers["kimi"].enabled)
        self.assertTrue(config.providers["deepseek"].enabled)



if __name__ == "__main__":
    unittest.main()
