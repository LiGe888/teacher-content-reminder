from __future__ import annotations

from teacher_content_reminder.config import AppConfig
from teacher_content_reminder.llm.base import LLMClient
from teacher_content_reminder.llm.mock import MockLLMClient
from teacher_content_reminder.llm.openai_compatible import OpenAICompatibleLLMClient
from teacher_content_reminder.llm.router import RouterLLMClient


def build_llm_client(config: AppConfig) -> LLMClient:
    provider = config.llm.provider.lower()
    if provider == "mock":
        return MockLLMClient(model=config.llm.model)
    if provider == "router":
        return _build_router_client(config, require_enabled=True)
    raise ValueError(
        f"Unsupported LLM provider '{config.llm.provider}'. "
        "Supported values are 'mock' and 'router'."
    )


def build_provider_client(config: AppConfig, provider_name: str, require_enabled: bool = False) -> LLMClient:
    name = provider_name.lower()
    if name == "mock":
        return MockLLMClient(model=config.llm.model)
    if name == "router":
        return _build_router_client(config, require_enabled=require_enabled)
    provider_config = config.providers.get(name)
    if provider_config is None:
        raise ValueError(f"Unknown provider '{provider_name}'.")
    if require_enabled and not provider_config.enabled:
        raise ValueError(f"Provider '{provider_name}' is disabled in config.")
    return OpenAICompatibleLLMClient(name=name, provider_config=provider_config, llm_config=config.llm)


def _build_router_client(config: AppConfig, require_enabled: bool) -> LLMClient:
    ordered_names = [config.llm.primary_provider, *config.llm.fallback_providers]
    clients: list[LLMClient] = []
    for name in ordered_names:
        provider_config = config.providers.get(name)
        if provider_config is None:
            continue
        if require_enabled and not provider_config.enabled:
            continue
        if not require_enabled and not provider_config.enabled and not provider_config.api_key():
            continue
        if not provider_config.api_key():
            continue
        clients.append(OpenAICompatibleLLMClient(name=name, provider_config=provider_config, llm_config=config.llm))
    if not clients:
        raise ValueError(
            "LLM router is enabled but no provider is available. "
            "Enable a provider in config or provide a matching API key in the environment."
        )
    return RouterLLMClient(clients, task_routes=config.llm.task_routes)
