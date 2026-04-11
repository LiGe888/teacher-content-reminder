from __future__ import annotations

from datetime import timedelta
from html import escape
import json
import os
from pathlib import Path

from teacher_content_reminder.config import AlertingConfig
from teacher_content_reminder.delivery import DingTalkBotClient
from teacher_content_reminder.repository import SQLiteRepository
from teacher_content_reminder.scheduler import local_now, localize_datetime


class AlertService:
    def __init__(
        self,
        config: AlertingConfig,
        repository: SQLiteRepository,
        timezone_name: str,
    ) -> None:
        self.config = config
        self.repository = repository
        self.timezone_name = timezone_name

    def is_enabled(self) -> bool:
        return self.config.enabled and bool(os.getenv(self.config.webhook_env, "").strip())

    def send_alert(
        self,
        *,
        category: str,
        severity: str,
        title: str,
        message: str,
        fingerprint: str,
        source_name: str = "",
        queue_id: int | None = None,
        package_id: int | None = None,
        payload: dict[str, object] | None = None,
        force: bool = False,
    ) -> dict[str, object]:
        details = dict(payload or {})
        details.update(
            {
                "category": category,
                "severity": severity,
                "fingerprint": fingerprint,
            }
        )

        if not self.config.enabled:
            self._record(
                status="disabled",
                title=title,
                message="Alerting disabled.",
                source_name=source_name,
                queue_id=queue_id,
                package_id=package_id,
                payload=details,
            )
            return {"sent": False, "status": "disabled"}

        webhook_url = os.getenv(self.config.webhook_env, "").strip()
        if not webhook_url:
            self._record(
                status="disabled",
                title=title,
                message=f"Missing alert webhook env {self.config.webhook_env}.",
                source_name=source_name,
                queue_id=queue_id,
                package_id=package_id,
                payload=details,
            )
            return {"sent": False, "status": "disabled"}

        if not force and self._is_suppressed(fingerprint):
            self._record(
                status="suppressed",
                title=title,
                message=f"Suppressed duplicate alert: {title}",
                source_name=source_name,
                queue_id=queue_id,
                package_id=package_id,
                payload=details,
            )
            return {"sent": False, "status": "suppressed"}

        secret = os.getenv(self.config.secret_env or "", "").strip() if self.config.secret_env else None
        detail_path = self._save_html_report(
            category=category,
            severity=severity,
            title=title,
            message=message,
            payload=details,
        )
        try:
            response = self._build_client(webhook_url=webhook_url, secret=secret).send_markdown(
                title=title,
                text=self._render_markdown(
                    category=category,
                    severity=severity,
                    title=title,
                    message=message,
                    source_name=source_name,
                    queue_id=queue_id,
                    package_id=package_id,
                    payload=details,
                    detail_path=detail_path,
                ),
            )
            status = "sent" if response.get("errcode") == 0 else "failed"
        except Exception as exc:  # pragma: no cover - network dependent
            response = {
                "error": str(exc),
                "exception_type": type(exc).__name__,
            }
            status = "failed"

        details["response"] = response
        self._record(
            status=status,
            title=title,
            message=message,
            source_name=source_name,
            queue_id=queue_id,
            package_id=package_id,
            payload=details,
        )
        return {
            "sent": status == "sent",
            "status": status,
            "response": response,
        }

    def _is_suppressed(self, fingerprint: str) -> bool:
        cutoff = local_now(self.timezone_name) - timedelta(minutes=self.config.min_interval_minutes)
        items = self.repository.list_activity_logs(event_type="alert", limit=100)
        for item in items:
            if item.status != "sent" or not item.created_at:
                continue
            if item.payload and item.payload.get("fingerprint") == fingerprint:
                created_at = localize_datetime(item.created_at, self.timezone_name)
                if created_at >= cutoff:
                    return True
        return False

    def _record(
        self,
        *,
        status: str,
        title: str,
        message: str,
        source_name: str,
        queue_id: int | None,
        package_id: int | None,
        payload: dict[str, object],
    ) -> None:
        self.repository.record_activity_log(
            event_type="alert",
            status=status,
            message=title,
            source_name=source_name,
            queue_id=queue_id,
            package_id=package_id,
            payload={
                "message": message,
                **payload,
            },
        )

    def _build_client(self, webhook_url: str, secret: str | None) -> DingTalkBotClient:
        return DingTalkBotClient(webhook_url=webhook_url, secret=secret)

    def _render_markdown(
        self,
        *,
        category: str,
        severity: str,
        title: str,
        message: str,
        source_name: str,
        queue_id: int | None,
        package_id: int | None,
        payload: dict[str, object],
        detail_path: Path | None,
    ) -> str:
        now_text = local_now(self.timezone_name).strftime("%Y-%m-%d %H:%M:%S %Z")
        lines = [
            f"## {title}",
            "",
            f"- Severity: `{severity}`",
            f"- Category: `{category}`",
            f"- Time: `{now_text}`",
        ]
        if source_name:
            lines.append(f"- Source: `{source_name}`")
        if queue_id is not None:
            lines.append(f"- Queue ID: `{queue_id}`")
        if package_id is not None:
            lines.append(f"- Package ID: `{package_id}`")
        lines.extend(
            [
                "",
                message,
            ]
        )
        detail_url = self._detail_url(detail_path)
        if detail_url:
            lines.extend(
                [
                    "",
                    f"🔗 [Open alert detail]({detail_url})",
                ]
            )
        payload_text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if len(payload_text) > 1600:
            payload_text = payload_text[:1600] + "\n... (truncated)"
        lines.extend(
            [
                "",
                "```json",
                payload_text,
                "```",
            ]
        )
        return "\n".join(lines)

    def _save_html_report(
        self,
        *,
        category: str,
        severity: str,
        title: str,
        message: str,
        payload: dict[str, object],
    ) -> Path:
        now = local_now(self.timezone_name)
        alerts_dir = Path(".data") / "alerts"
        alerts_dir.mkdir(parents=True, exist_ok=True)
        filename = f"alert_{now.strftime('%Y%m%d_%H%M%S_%f')}.html"
        payload_text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{escape(title)}</title>
    <style>
      body {{
        margin: 0;
        padding: 24px;
        background: #0f172a;
        color: #e2e8f0;
        font-family: "SFMono-Regular", "Menlo", monospace;
      }}
      main {{
        max-width: 960px;
        margin: 0 auto;
      }}
      h1 {{
        margin: 0 0 12px;
      }}
      .meta {{
        color: #93c5fd;
        line-height: 1.8;
      }}
      pre {{
        white-space: pre-wrap;
        word-break: break-word;
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 16px;
        padding: 16px;
      }}
      .message {{
        margin: 20px 0;
        padding: 16px;
        border-radius: 16px;
        background: rgba(30, 41, 59, 0.85);
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>{escape(title)}</h1>
      <div class="meta">
        <div>Severity: {escape(severity)}</div>
        <div>Category: {escape(category)}</div>
        <div>Time: {escape(now.strftime("%Y-%m-%d %H:%M:%S %Z"))}</div>
      </div>
      <div class="message">{escape(message)}</div>
      <pre>{escape(payload_text)}</pre>
    </main>
  </body>
</html>
"""
        path = alerts_dir / filename
        path.write_text(html, encoding="utf-8")
        return path

    def _detail_url(self, path: Path | None) -> str | None:
        if path is None:
            return None
        base_url = os.getenv("ALERT_VIEW_HOST", "").rstrip("/")
        if not base_url:
            return None
        return f"{base_url}/alerts/{path.name}"
