from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    provider: str
    model: str

    @abstractmethod
    def generate(self, task_name: str, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

