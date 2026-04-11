from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any
import tomllib


@dataclass(slots=True)
class ProjectConfig:
    name: str
    timezone: str = "Asia/Shanghai"
    default_review_mode: str = "manual"
    max_daily_push: int = 3


@dataclass(slots=True)
class SelectionConfig:
    freshness_hours: int = 72
    min_total_score: float = 75.0
    queue_review_score_min: float = 60.0
    content_mix: dict[str, float] | None = None


@dataclass(slots=True)
class AudienceConfig:
    cefr: str
    passage_words: tuple[int, int]
    question_count: int
    cloze_blanks: int


@dataclass(slots=True)
class ExerciseProfileConfig:
    enabled: tuple[str, ...]
    include_answers: bool = True
    include_explanations: bool = True


@dataclass(slots=True)
class DeliveryConfig:
    channel: str
    template: str
    webhook_env: str
    secret_env: str | None = None


@dataclass(slots=True)
class AlertingConfig:
    enabled: bool = False
    channel: str = "dingtalk"
    webhook_env: str = "DINGTALK_ALERT_WEBHOOK_URL"
    secret_env: str | None = "DINGTALK_ALERT_SECRET"
    min_interval_minutes: int = 30
    notify_dispatch_failure: bool = True
    notify_source_failure: bool = True
    notify_scheduled_failure: bool = True


@dataclass(slots=True)
class ReviewConfig:
    auto_approve_score: float = 82.0
    special_push_score: float = 90.0
    limit_per_source: int = 1


@dataclass(slots=True)
class ScheduleConfig:
    weekday_only: bool = True
    morning_send_time: str = "07:30"
    evening_send_time: str = "20:30"
    allow_evening_send: bool = True
    evening_requires_special: bool = True
    min_hours_between_push: int = 6
    send_window_minutes: int = 30


@dataclass(slots=True)
class LLMConfig:
    provider: str = "router"
    model: str = "mock-teacher-v1"
    api_key_env: str = "OPENAI_API_KEY"
    api_base_env: str = "OPENAI_BASE_URL"
    timeout_seconds: int = 60
    temperature: float = 0.2
    primary_provider: str = "qwen"
    fallback_providers: tuple[str, ...] = ("kimi", "deepseek")
    system_prompt: str = (
        "You are a careful curriculum-content generator. "
        "Always respond with a single JSON object and do not add extra prose."
    )
    max_retries: int = 1
    task_routes: dict[str, tuple[str, ...]] | None = None


@dataclass(slots=True)
class ProviderConfig:
    enabled: bool
    base_url: str
    model: str
    api_key_env: str
    timeout_seconds: int = 60
    temperature: float = 0.2
    json_mode: bool = True
    extra_body: dict[str, Any] | None = None

    def api_key(self) -> str | None:
        value = os.getenv(self.api_key_env)
        return value.strip() if value else None


@dataclass(slots=True)
class GenerationConfig:
    default_audience: str = "senior"
    default_exercise_profile: str = "default"
    max_input_chars: int = 12000


@dataclass(slots=True)
class SourceConfig:
    name: str
    category: str
    type: str
    entry_url: str
    enabled: bool = True
    priority: int = 0
    schedule_cron: str = "0 * * * *"


@dataclass(slots=True)
class AppConfig:
    project: ProjectConfig
    selection: SelectionConfig
    audiences: dict[str, AudienceConfig]
    exercise_profiles: dict[str, ExerciseProfileConfig]
    delivery: DeliveryConfig
    alerting: AlertingConfig
    review: ReviewConfig
    schedule: ScheduleConfig
    llm: LLMConfig
    providers: dict[str, ProviderConfig]
    generation: GenerationConfig
    sources: dict[str, SourceConfig]

    def get_source(self, name: str) -> SourceConfig:
        try:
            return self.sources[name]
        except KeyError as exc:
            raise KeyError(f"Unknown source: {name}") from exc

    @property
    def enabled_sources(self) -> list[SourceConfig]:
        sources = [source for source in self.sources.values() if source.enabled]
        return sorted(sources, key=lambda item: (-item.priority, item.name))


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "default.toml"


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path) if path else default_config_path()
    _load_dotenv(config_path.parent.parent / ".env")
    raw = _load_toml(config_path)

    project = ProjectConfig(**raw["project"])
    selection = SelectionConfig(**raw["selection"])

    audiences = {
        name: AudienceConfig(
            cefr=value["cefr"],
            passage_words=tuple(value["passage_words"]),
            question_count=int(value["question_count"]),
            cloze_blanks=int(value["cloze_blanks"]),
        )
        for name, value in raw.get("audiences", {}).items()
    }

    exercise_profiles = {
        name: ExerciseProfileConfig(
            enabled=tuple(value.get("enabled", [])),
            include_answers=bool(value.get("include_answers", True)),
            include_explanations=bool(value.get("include_explanations", True)),
        )
        for name, value in raw.get("exercise_profiles", {}).items()
    }

    delivery = DeliveryConfig(**raw["delivery"])
    alerting = AlertingConfig(**raw.get("alerting", {}))
    review = ReviewConfig(**raw.get("review", {}))
    schedule = ScheduleConfig(**raw.get("schedule", {}))
    llm_raw = dict(raw.get("llm", {}))
    llm_raw["fallback_providers"] = tuple(llm_raw.get("fallback_providers", ()))
    llm_raw["task_routes"] = {
        task_name: tuple(provider_names)
        for task_name, provider_names in llm_raw.get("task_routes", {}).items()
    } or None
    llm = LLMConfig(**llm_raw)
    providers = {
        name: ProviderConfig(
            enabled=bool(value.get("enabled", False)),
            base_url=value["base_url"],
            model=value["model"],
            api_key_env=value["api_key_env"],
            timeout_seconds=int(value.get("timeout_seconds", 60)),
            temperature=float(value.get("temperature", llm.temperature)),
            json_mode=bool(value.get("json_mode", True)),
            extra_body=dict(value.get("extra_body", {})) or None,
        )
        for name, value in raw.get("providers", {}).items()
    }
    generation = GenerationConfig(**raw.get("generation", {}))
    sources = {item["name"]: SourceConfig(**item) for item in raw.get("sources", [])}

    return AppConfig(
        project=project,
        selection=selection,
        audiences=audiences,
        exercise_profiles=exercise_profiles,
        delivery=delivery,
        alerting=alerting,
        review=review,
        schedule=schedule,
        llm=llm,
        providers=providers,
        generation=generation,
        sources=sources,
    )


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
