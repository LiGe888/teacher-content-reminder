from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from tenacity import Retrying, wait_exponential, stop_after_attempt, retry_if_exception
except ImportError as exc:
    raise RuntimeError("tenacity is not installed. Please run `pip install tenacity`.") from exc
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from teacher_content_reminder.config import LLMConfig, ProviderConfig
from teacher_content_reminder.llm.base import LLMClient
from teacher_content_reminder.llm.errors import (
    LLMError,
    classify_http_error,
    classify_network_error,
    response_parse_error,
)


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(self, name: str, provider_config: ProviderConfig, llm_config: LLMConfig) -> None:
        self.provider = name
        self.model = provider_config.model
        self.provider_config = provider_config
        self.llm_config = llm_config

    def generate(self, task_name: str, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        api_key = self.provider_config.api_key()
        if not api_key:
            raise ValueError(f"Missing API key for provider '{self.provider}' in env '{self.provider_config.api_key_env}'.")

        def _is_retryable(exc: BaseException) -> bool:
            return getattr(exc, "retryable", False)

        for attempt in Retrying(
            wait=wait_exponential(multiplier=1, min=2, max=10),
            stop=stop_after_attempt(self.llm_config.max_retries + 1),
            retry=retry_if_exception(_is_retryable),
            reraise=True
        ):
            with attempt:
                payload = {
                    "model": self.provider_config.model,
                    "messages": [
                        {"role": "system", "content": self.llm_config.system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"Task: {task_name}\n"
                                f"Return only a valid JSON object.\n\n"
                                f"{prompt}"
                            ),
                        },
                    ],
                    "temperature": self.provider_config.temperature,
                }
                if self.provider_config.json_mode:
                    payload["response_format"] = {"type": "json_object"}
                if self.provider_config.extra_body:
                    payload.update(self.provider_config.extra_body)

                response = _post_json(
                    provider=self.provider,
                    url=f"{self.provider_config.base_url.rstrip('/')}/chat/completions",
                    api_key=api_key,
                    payload=payload,
                    timeout=self.provider_config.timeout_seconds,
                )
                try:
                    content = response["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise response_parse_error(self.provider, "missing choices[0].message.content") from exc
                return _parse_json_content(self.provider, content)


def _post_json(provider: str, url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
            return json.loads(body)
    except HTTPError as exc:  # pragma: no cover - network dependent
        detail = exc.read().decode("utf-8", errors="replace")
        raise classify_http_error(provider, exc.code, detail) from exc
    except URLError as exc:  # pragma: no cover - network dependent
        raise classify_network_error(provider, str(exc)) from exc


def _parse_json_content(provider: str, content: Any) -> dict[str, Any]:
    if isinstance(content, list):
        merged = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        )
        content = merged
    if not isinstance(content, str):
        raise ValueError("Model response content is not a string.")
    text = content.strip()
    if not text:
        raise ValueError("Model response content is empty.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            candidate = _extract_json_object(text)
            return json.loads(candidate)
        except Exception as exc:
            raise response_parse_error(provider, text[:300]) from exc


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Unable to locate JSON object in model response.")
    return text[start : end + 1]
