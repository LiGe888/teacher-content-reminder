from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from teacher_content_reminder.config import AppConfig
from teacher_content_reminder.models import DeliveryEvent


@dataclass(slots=True)
class DispatchDecision:
    allowed: bool
    reason: str
    slot: str | None = None


def localize_datetime(value: datetime, timezone_name: str) -> datetime:
    zone = ZoneInfo(timezone_name)
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def local_now(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def cron_matches(expression: str, current: datetime) -> bool:
    parts = expression.split()
    if len(parts) != 5:
        return False
    minute, hour, _, _, weekday = parts
    weekday_value = (current.weekday() + 1) % 7
    return (
        _field_matches(minute, current.minute)
        and _field_matches(hour, current.hour)
        and _field_matches(weekday, weekday_value)
    )


def due_source_names(config: AppConfig, current: datetime, force: bool = False) -> list[str]:
    if force:
        return [source.name for source in config.enabled_sources]
    localized = localize_datetime(current, config.project.timezone)
    return [
        source.name
        for source in config.enabled_sources
        if source.auto_queue_enabled
        if cron_matches(source.schedule_cron, localized)
    ]


def review_recommendation(config: AppConfig, score_total: float) -> str:
    if score_total < config.selection.queue_review_score_min:
        return "discard"
    if score_total >= config.review.special_push_score:
        return "special"
    if score_total >= config.review.auto_approve_score:
        return "auto_send"
    return "review"


def initial_queue_status(config: AppConfig, recommendation: str) -> str:
    mode = config.project.default_review_mode.lower()
    if recommendation == "discard":
        return "discarded"
    if mode in {"auto", "hybrid"} and recommendation in {"auto_send", "special"}:
        return "approved"
    return "pending_review"


def dispatch_decision(
    config: AppConfig,
    now: datetime,
    sent_today_count: int,
    last_event: DeliveryEvent | None,
    force: bool = False,
) -> DispatchDecision:
    localized = localize_datetime(now, config.project.timezone)
    if force:
        return DispatchDecision(True, "forced", slot="forced")
    if config.schedule.weekday_only and localized.weekday() >= 5:
        return DispatchDecision(False, "outside_weekday_window")
    if sent_today_count >= config.project.max_daily_push:
        return DispatchDecision(False, "daily_limit_reached")
    slot = _current_slot(config, localized)
    if slot is None:
        return DispatchDecision(False, "outside_send_window")
    if last_event and last_event.created_at:
        last_local = localize_datetime(last_event.created_at, config.project.timezone)
        min_gap = timedelta(hours=config.schedule.min_hours_between_push)
        if localized - last_local < min_gap:
            return DispatchDecision(False, "minimum_gap_not_reached", slot=slot)
    return DispatchDecision(True, "ok", slot=slot)


def _current_slot(config: AppConfig, current: datetime) -> str | None:
    if _within_window(current, config.schedule.morning_send_time, config.schedule.send_window_minutes):
        return "morning"
    if config.schedule.allow_evening_send and _within_window(
        current,
        config.schedule.evening_send_time,
        config.schedule.send_window_minutes,
    ):
        return "evening"
    return None


def _within_window(current: datetime, scheduled: str, window_minutes: int) -> bool:
    target = _parse_time(scheduled)
    target_dt = current.replace(hour=target.hour, minute=target.minute, second=0, microsecond=0)
    delta = abs((current - target_dt).total_seconds())
    return delta <= window_minutes * 60


def _parse_time(value: str) -> time:
    hour_text, minute_text = value.split(":", 1)
    return time(hour=int(hour_text), minute=int(minute_text))


def _field_matches(expression: str, value: int) -> bool:
    expression = expression.strip()
    if expression == "*":
        return True
    if expression.startswith("*/"):
        interval = int(expression[2:])
        return interval > 0 and value % interval == 0
    if "," in expression:
        return any(_field_matches(part, value) for part in expression.split(","))
    return int(expression) == value
