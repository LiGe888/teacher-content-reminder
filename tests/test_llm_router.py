import unittest
from unittest.mock import patch

from teacher_content_reminder.config import load_config
from teacher_content_reminder.llm.factory import build_provider_client
from teacher_content_reminder.llm.base import LLMClient
from teacher_content_reminder.llm.mock import MockLLMClient
from teacher_content_reminder.llm.router import RouterLLMClient
from teacher_content_reminder.llm.smoke_test import run_smoke_test


class _FailClient(LLMClient):
    provider = "fail"
    model = "fail-model"

    def generate(self, task_name: str, prompt: str, context: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("boom")


class _SuccessClient(LLMClient):
    provider = "ok"
    model = "ok-model"

    def generate(self, task_name: str, prompt: str, context: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "task_name": task_name}


class RouterTests(unittest.TestCase):
    def test_router_falls_back_to_next_client(self) -> None:
        client = RouterLLMClient([_FailClient(), _SuccessClient()])
        result = client.generate("extract_facts", "{}", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["task_name"], "extract_facts")

    def test_smoke_test_works_with_mock_client(self) -> None:
        payload = run_smoke_test(MockLLMClient())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "smoke_test")

    def test_build_provider_client_supports_router_override(self) -> None:
        config = load_config("config/default.toml")
        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "test-qwen",
                "MOONSHOT_API_KEY": "test-kimi",
                "DEEPSEEK_API_KEY": "",
            },
            clear=False,
        ):
            client = build_provider_client(config, "router", require_enabled=False)
        self.assertIsInstance(client, RouterLLMClient)
        self.assertEqual([item.provider for item in client.ordered_clients("extract_facts")][:2], ["qwen", "kimi"])


if __name__ == "__main__":
    unittest.main()
