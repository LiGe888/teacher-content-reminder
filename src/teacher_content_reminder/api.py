from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import HTMLResponse
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "FastAPI is not installed. Run `pip3 install -e \".[api]\"` before starting the API server."
    ) from exc

from teacher_content_reminder.pipeline import ContentPipeline
from teacher_content_reminder.review_dashboard import (
    activity_log_payload,
    generated_preview_payload,
    render_review_dashboard,
    review_queue_payload,
    to_jsonable,
)


def create_app() -> FastAPI:
    pipeline = ContentPipeline()
    pipeline.initialize()

    app = FastAPI(title="Teacher Content Reminder", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    @app.get("/review", response_class=HTMLResponse)
    def review_dashboard_page() -> HTMLResponse:
        sources = [asdict(source) for source in pipeline.config.enabled_sources]
        default_source = str(sources[0]["name"]) if sources else None
        return HTMLResponse(render_review_dashboard(sources=sources, default_source=default_source))

    @app.get("/sources")
    def list_sources() -> list[dict[str, object]]:
        return [asdict(source) for source in pipeline.config.enabled_sources]

    @app.get("/api/sources")
    def api_list_sources() -> list[dict[str, object]]:
        return [asdict(source) for source in pipeline.config.enabled_sources]

    @app.get("/preview/{source_name}")
    def preview(source_name: str, limit: int = Query(default=3, ge=1, le=10)) -> list[dict[str, object]]:
        try:
            items = pipeline.preview_source(source_name, limit=limit, persist=False)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [
            {
                "candidate": asdict(item.candidate),
                "article": asdict(item.article),
                "score": asdict(item.score),
            }
            for item in items
        ]

    @app.get("/generate/{source_name}")
    def generate_preview(
        source_name: str,
        audience: str = Query(default="senior", pattern="^(junior|senior|adult)$"),
        limit: int = Query(default=1, ge=1, le=5),
    ) -> list[dict[str, object]]:
        try:
            items = pipeline.generate_preview_source(
                source_name=source_name,
                audience=audience,
                limit=limit,
                persist=False,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [
            {
                "preview": {
                    "candidate": asdict(item.preview.candidate),
                    "article": asdict(item.preview.article),
                    "score": asdict(item.preview.score),
                },
                "package": asdict(item.package),
            }
            for item in items
        ]

    @app.get("/api/review-queue")
    def api_review_queue(
        status: str | None = Query(default=None),
        recommendation: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> list[dict[str, object]]:
        items = pipeline.list_review_queue(status=status, recommendation=recommendation, limit=limit)
        return [review_queue_payload(item) for item in items]

    @app.get("/api/dashboard-summary")
    def api_dashboard_summary() -> dict[str, object]:
        return to_jsonable(pipeline.get_dashboard_summary())

    @app.get("/api/activity-log")
    def api_activity_log(
        event_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=30, ge=1, le=100),
    ) -> list[dict[str, object]]:
        items = pipeline.list_activity_logs(event_type=event_type, status=status, limit=limit)
        return [activity_log_payload(item) for item in items]

    @app.get("/api/review-queue/{queue_id}")
    def api_review_queue_detail(queue_id: int) -> dict[str, object]:
        try:
            detail = pipeline.get_review_queue_detail(queue_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return review_queue_payload(detail["queue_item"], generated=detail["generated"])

    @app.post("/api/queue/{source_name}")
    def api_queue_source(
        source_name: str,
        audience: str = Query(default="senior", pattern="^(junior|senior|adult)$"),
        exercise_profile: str | None = Query(default=None),
        provider: str | None = Query(default=None),
        limit: int | None = Query(default=None, ge=1, le=5),
    ) -> list[dict[str, object]]:
        try:
            items = pipeline.queue_source_for_review(
                source_name=source_name,
                audience=audience,
                exercise_profile=exercise_profile,
                provider=provider,
                limit=limit,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [review_queue_payload(item) for item in items]

    @app.post("/api/review-queue/{queue_id}/approve")
    async def api_review_approve(queue_id: int, request: Request) -> dict[str, object]:
        payload = await _request_payload(request)
        try:
            result = pipeline.approve_review_item(
                queue_id=queue_id,
                reviewer_note=str(payload.get("note", "")),
                send=bool(payload.get("send", False)),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_jsonable(result)

    @app.post("/api/review-queue/{queue_id}/reject")
    async def api_review_reject(queue_id: int, request: Request) -> dict[str, object]:
        payload = await _request_payload(request)
        try:
            item = pipeline.reject_review_item(
                queue_id=queue_id,
                reviewer_note=str(payload.get("note", "")),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return review_queue_payload(item)

    @app.post("/api/review-queue/{queue_id}/dispatch")
    async def api_review_dispatch(queue_id: int, request: Request) -> dict[str, object]:
        payload = await _request_payload(request)
        try:
            result = pipeline.dispatch_queue_item(
                queue_id=queue_id,
                send=bool(payload.get("send", False)),
                force=bool(payload.get("force", False)),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_jsonable(result)

    @app.post("/api/scheduled/run")
    async def api_run_scheduled(request: Request) -> dict[str, object]:
        payload = await _request_payload(request)
        try:
            result = pipeline.run_scheduled(
                now=_parse_datetime(payload.get("now")),
                audience=_optional_text(payload.get("audience")),
                exercise_profile=_optional_text(payload.get("exercise_profile")),
                provider=_optional_text(payload.get("provider")),
                limit_per_source=_optional_int(payload.get("limit_per_source")),
                source_names=_optional_string_list(payload.get("source_names")),
                force_sources=bool(payload.get("force_sources", False)),
                send=bool(payload.get("send", False)),
                force_dispatch=bool(payload.get("force_dispatch", False)),
                max_dispatch_items=_optional_int(payload.get("max_dispatch_items")) or 1,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_jsonable(result)

    # --- Alert viewer routes ---
    # Resolve alerts directory relative to the project root (config/../.data/alerts)
    from teacher_content_reminder.config import default_config_path as _default_cfg
    _alerts_base = _default_cfg().resolve().parent.parent / ".data" / "alerts"

    @app.get("/alerts", response_class=HTMLResponse)
    def list_alerts() -> HTMLResponse:
        """List all saved alert reports."""
        _alerts_base.mkdir(parents=True, exist_ok=True)
        files = sorted(_alerts_base.glob("alert_*.html"), reverse=True)
        rows = ""
        for f in files[:50]:
            rows += f'<tr><td><a href="/alerts/{f.name}">{f.name}</a></td><td>{f.stat().st_size} bytes</td></tr>\n'
        if not rows:
            rows = '<tr><td colspan="2" style="color:#8b949e;">暂无告警记录 ✅</td></tr>'
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>告警历史</title>
<style>body{{font-family:sans-serif;background:#0d1117;color:#e6edf3;padding:24px;max-width:900px;margin:0 auto}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #30363d;padding:12px;text-align:left}}
th{{background:#161b22}}a{{color:#58a6ff;text-decoration:none}}a:hover{{text-decoration:underline}}
h1{{border-bottom:2px solid #ff6b6b33;padding-bottom:12px}}</style></head>
<body><h1>🚨 告警历史记录</h1><p style="color:#8b949e">共 {len(files)} 条记录</p>
<table><tr><th>告警报告</th><th>大小</th></tr>{rows}</table></body></html>"""
        return HTMLResponse(html)

    @app.get("/alerts/{filename}", response_class=HTMLResponse)
    def view_alert(filename: str) -> HTMLResponse:
        """Serve a saved alert detail HTML page."""
        file_path = _alerts_base / filename
        if not file_path.exists() or not file_path.name.startswith("alert_"):
            raise HTTPException(status_code=404, detail="Alert not found")
        return HTMLResponse(file_path.read_text(encoding="utf-8"))

    _exports_base = _default_cfg().resolve().parent.parent / ".exports"

    @app.get("/exports/{file_path:path}")
    def view_export(file_path: str):
        """Serve exported HTML or PDF worksheets."""
        from fastapi.responses import FileResponse
        safe_path = (_exports_base / file_path).resolve()
        if not str(safe_path).startswith(str(_exports_base.resolve())):
            raise HTTPException(status_code=403, detail="Forbidden")
        if not safe_path.exists() or not safe_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(safe_path)

    return app


async def _request_payload(request: Request) -> dict[str, Any]:
    if not request.headers.get("content-type", "").startswith("application/json"):
        return {}
    try:
        payload = await request.json()
    except Exception:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Expected ISO datetime string.")
    return datetime.fromisoformat(value)


def _optional_text(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_string_list(value: object) -> list[str] | None:
    if value is None or value == "":
        return None
    if not isinstance(value, list):
        raise ValueError("Expected a list of source names.")
    return [str(item) for item in value if str(item).strip()]


app = create_app()
