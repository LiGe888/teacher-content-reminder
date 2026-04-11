from __future__ import annotations

from dataclasses import asdict
import os

from teacher_content_reminder.config import AppConfig
from teacher_content_reminder.llm.factory import build_provider_client
from teacher_content_reminder.llm.smoke_test import run_smoke_test


def build_runtime_report(config: AppConfig) -> dict[str, object]:
    enabled_provider_count = 0
    available_provider_count = 0
    provider_rows: list[dict[str, object]] = []
    for name, provider in config.providers.items():
        key_present = bool(provider.api_key())
        if provider.enabled:
            enabled_provider_count += 1
            if key_present:
                available_provider_count += 1
        provider_rows.append(
            {
                "name": name,
                "enabled": provider.enabled,
                "model": provider.model,
                "base_url": provider.base_url,
                "api_key_env": provider.api_key_env,
                "api_key_present": key_present,
                "json_mode": provider.json_mode,
            }
        )

    delivery = {
        "channel": config.delivery.channel,
        "template": config.delivery.template,
        "webhook_env": config.delivery.webhook_env,
        "webhook_present": bool(os.getenv(config.delivery.webhook_env)),
        "secret_env": config.delivery.secret_env,
        "secret_present": bool(os.getenv(config.delivery.secret_env or "")) if config.delivery.secret_env else False,
    }
    alerting = {
        "enabled": config.alerting.enabled,
        "channel": config.alerting.channel,
        "webhook_env": config.alerting.webhook_env,
        "webhook_present": bool(os.getenv(config.alerting.webhook_env)),
        "secret_env": config.alerting.secret_env,
        "secret_present": bool(os.getenv(config.alerting.secret_env or "")) if config.alerting.secret_env else False,
        "min_interval_minutes": config.alerting.min_interval_minutes,
    }

    missing_items: list[str] = []
    if config.llm.provider == "router" and enabled_provider_count == 0:
        missing_items.append("No provider is enabled under [providers.*].")
    if config.llm.provider == "router" and available_provider_count == 0:
        missing_items.append("No API key is present for any enabled provider in the router chain.")
    if not delivery["webhook_present"]:
        missing_items.append(f"Missing env {config.delivery.webhook_env} for DingTalk delivery.")
    if delivery["secret_env"] and not delivery["secret_present"]:
        missing_items.append(f"Missing env {config.delivery.secret_env} for DingTalk delivery.")
    if alerting["enabled"] and not alerting["webhook_present"]:
        missing_items.append(f"Missing env {config.alerting.webhook_env} for alert delivery.")
    if alerting["enabled"] and alerting["secret_env"] and not alerting["secret_present"]:
        missing_items.append(f"Missing env {config.alerting.secret_env} for alert delivery.")

    return {
        "llm": {
            "provider_mode": config.llm.provider,
            "primary_provider": config.llm.primary_provider,
            "fallback_providers": list(config.llm.fallback_providers),
            "task_routes": {
                key: list(value) for key, value in (config.llm.task_routes or {}).items()
            },
            "enabled_provider_count": enabled_provider_count,
            "available_provider_count": available_provider_count,
        },
        "providers": provider_rows,
        "delivery": delivery,
        "alerting": alerting,
        "generation": asdict(config.generation),
        "missing_items": missing_items,
        "ready": len(missing_items) == 0,
    }


def build_beta_report(config: AppConfig, live: bool = False) -> dict[str, object]:
    runtime = build_runtime_report(config)
    router_chain = [config.llm.primary_provider, *config.llm.fallback_providers]
    router_rows: list[dict[str, object]] = []

    for index, provider_name in enumerate(router_chain):
        provider = config.providers.get(provider_name)
        if provider is None:
            continue
        row: dict[str, object] = {
            "name": provider_name,
            "role": "primary" if index == 0 else f"fallback_{index}",
            "model": provider.model,
            "api_key_present": bool(provider.api_key()),
            "enabled": provider.enabled,
        }
        if live and row["api_key_present"]:
            try:
                client = build_provider_client(config, provider_name, require_enabled=False)
                payload = run_smoke_test(client)
                row["live_ok"] = True
                row["live_status"] = "ok"
                row["live_message"] = payload.get("message", "")
            except Exception as exc:  # pragma: no cover - network dependent
                row["live_ok"] = False
                row["live_status"] = getattr(exc, "kind", "error")
                row["live_error"] = str(exc)
        elif live:
            row["live_ok"] = False
            row["live_status"] = "skipped_no_key"
        router_rows.append(row)

    ready_generation = any(bool(row["api_key_present"]) for row in router_rows)
    if live:
        ready_generation = any(bool(row.get("live_ok")) for row in router_rows)

    delivery = runtime["delivery"]
    alerting = runtime["alerting"]
    ready_delivery = bool(ready_generation and delivery["webhook_present"] and delivery["secret_present"])
    ready_alerting = bool(
        (not alerting["enabled"])
        or (alerting["webhook_present"] and (not alerting["secret_env"] or alerting["secret_present"]))
    )

    missing_items = list(runtime["missing_items"])
    if not any(bool(row["api_key_present"]) for row in router_rows):
        missing_items.append("No API key is present for any provider in the router chain.")
    if live and not any(bool(row.get("live_ok")) for row in router_rows):
        missing_items.append("No live provider smoke test succeeded in the router chain.")

    return {
        "router_chain": router_rows,
        "delivery": delivery,
        "alerting": alerting,
        "live_requested": live,
        "ready_generation": ready_generation,
        "ready_delivery": ready_delivery,
        "ready_alerting": ready_alerting,
        "missing_items": missing_items,
        "ready": len(missing_items) == 0 if live else ready_generation and ready_delivery and ready_alerting,
    }
