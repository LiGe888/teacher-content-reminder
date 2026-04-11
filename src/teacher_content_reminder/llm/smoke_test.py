from __future__ import annotations

from teacher_content_reminder.llm.base import LLMClient


def run_smoke_test(client: LLMClient) -> dict[str, object]:
    prompt = """
Return a JSON object with the following keys:
- ok: boolean true
- provider: string
- mode: "smoke_test"
- message: short string confirming JSON output works
""".strip()
    payload = client.generate("smoke_test", prompt, {})
    if payload.get("ok") is not True:
        raise ValueError("Smoke test response did not set ok=true.")
    return payload
