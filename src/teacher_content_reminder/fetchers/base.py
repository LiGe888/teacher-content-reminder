from __future__ import annotations

from abc import ABC, abstractmethod

from teacher_content_reminder.config import SourceConfig
from teacher_content_reminder.models import ArticleCandidate


class SourceFetcher(ABC):
    @abstractmethod
    def fetch(self, source: SourceConfig, limit: int = 10) -> list[ArticleCandidate]:
        raise NotImplementedError

