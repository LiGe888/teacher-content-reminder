from __future__ import annotations

from typing import Iterable

from teacher_content_reminder.llm.base import LLMClient


class RouterLLMClient(LLMClient):
    provider = "router"

    def __init__(
        self,
        clients: Iterable[LLMClient],
        task_routes: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.clients = list(clients)
        if not self.clients:
            raise ValueError("RouterLLMClient requires at least one downstream client.")
        self.clients_by_name = {client.provider: client for client in self.clients}
        self.default_order = [client.provider for client in self.clients]
        self.task_routes = task_routes or {}
        self.model = " -> ".join(f"{client.provider}:{client.model}" for client in self.clients)

    def generate(self, task_name: str, prompt: str, context: dict[str, object]) -> dict[str, object]:
        errors: list[str] = []
        for client in self.ordered_clients(task_name):
            try:
                return client.generate(task_name, prompt, context)
            except Exception as exc:
                errors.append(f"{client.provider}:{exc}")
        raise RuntimeError("All configured LLM providers failed. " + " | ".join(errors))

    def ordered_clients(self, task_name: str) -> list[LLMClient]:
        route = self.task_routes.get(task_name)
        if not route:
            return self.clients

        ordered: list[LLMClient] = []
        seen: set[str] = set()
        for provider_name in route:
            client = self.clients_by_name.get(provider_name)
            if client is None:
                continue
            ordered.append(client)
            seen.add(provider_name)
        for provider_name in self.default_order:
            if provider_name in seen:
                continue
            ordered.append(self.clients_by_name[provider_name])
        return ordered
