from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
import html
import json
import os
from pathlib import Path

from teacher_content_reminder.config import default_config_path
from teacher_content_reminder.models import ActivityLogEntry, GeneratedPreviewItem, ReviewQueueItem


def to_jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def generated_preview_payload(item: GeneratedPreviewItem) -> dict[str, object]:
    return {
        "preview": to_jsonable(item.preview),
        "package": to_jsonable(item.package),
    }


def _exports_base_dir() -> Path:
    return default_config_path().resolve().parent.parent / ".exports"


def build_export_urls(export_directory: str) -> dict[str, str]:
    base_url = os.getenv("ALERT_VIEW_HOST", "").strip().rstrip("/")
    if not export_directory or not base_url:
        return {}

    exports_base = _exports_base_dir().resolve()
    export_path = Path(export_directory)
    if not export_path.is_absolute():
        export_path = (exports_base.parent / export_path).resolve()
    else:
        export_path = export_path.resolve()

    if not str(export_path).startswith(str(exports_base)):
        return {}

    files = {
        "teacher_html": export_path / "teacher_worksheet.html",
        "student_html": export_path / "student_worksheet.html",
        "package_json": export_path / "package.json",
    }
    urls: dict[str, str] = {}
    for key, file_path in files.items():
        if not file_path.exists():
            continue
        relative_path = file_path.relative_to(exports_base).as_posix()
        urls[key] = f"{base_url}/exports/{relative_path}"
    return urls


def review_queue_payload(
    item: ReviewQueueItem,
    generated: GeneratedPreviewItem | None = None,
) -> dict[str, object]:
    payload = {
        "queue": to_jsonable(item),
        "export_urls": build_export_urls(item.export_directory),
    }
    if generated is not None:
        payload["generated"] = generated_preview_payload(generated)
    return payload


def activity_log_payload(item: ActivityLogEntry) -> dict[str, object]:
    return {
        "activity": to_jsonable(item),
    }


def render_review_dashboard(
    sources: list[dict[str, object]],
    default_source: str | None = None,
) -> str:
    normalized_default = default_source or (str(sources[0]["name"]) if sources else "")
    source_options = "\n".join(
        f'<option value="{html.escape(str(source["name"]))}">{html.escape(str(source["name"]))}</option>'
        for source in sources
    )
    audience_options = "\n".join(
        [
            '<option value="senior">senior</option>',
            '<option value="adult">adult</option>',
            '<option value="junior">junior</option>',
        ]
    )
    provider_options = "\n".join(
        [
            '<option value="router">router</option>',
            '<option value="qwen">qwen</option>',
            '<option value="kimi">kimi</option>',
            '<option value="deepseek">deepseek</option>',
            '<option value="mock">mock</option>',
        ]
    )
    translations = {
        "en": {
            "page_title": "Teacher Content Review",
            "hero_title": "Teacher Review Desk",
            "hero_subtitle": "Queue fresh teaching content, inspect the generated worksheet package, then approve, reject, or send it to DingTalk without leaving the page.",
            "hero_export_title": "Export Entry",
            "hero_export_hint": "Select a queue item first, then open the latest teacher HTML directly from here.",
            "hero_export_open": "Open Teacher HTML",
            "hero_export_open_disabled": "Select Item To Export",
            "language_label": "Language",
            "summary_pending_title": "Pending Review",
            "summary_pending_note": "Waiting for teacher approval.",
            "summary_approved_title": "Approved Queue",
            "summary_approved_note": "Ready for the next send window.",
            "summary_sent_title": "Sent Today",
            "summary_sent_note": "Daily rhythm stays visible here.",
            "summary_dispatch_title": "Latest Dispatch",
            "summary_dispatch_note": "No dispatch activity yet.",
            "summary_alerts_title": "Alerts",
            "summary_alerts_note": "No failed activity right now.",
            "summary_alerts_action": "Click to view full alert history.",
            "label_source": "Source",
            "label_audience": "Audience",
            "label_provider": "Provider",
            "label_queue_filter": "Queue Filter",
            "label_actions": "Actions",
            "action_queue_source": "Queue Source",
            "action_refresh_queue": "Refresh Queue",
            "label_review_queue": "Review Queue",
            "queue_status_initial": "Queue not loaded yet.",
            "queue_empty_initial": "No queue data yet.",
            "label_package_detail": "Package Detail",
            "no_selection": "no selection",
            "detail_empty_initial": "Select a queue item to inspect the generated material.",
            "label_reviewer_note": "Reviewer Note",
            "reviewer_note_placeholder": "Add a short reviewer note before approving or rejecting.",
            "action_approve": "Approve",
            "action_approve_send": "Approve + Send",
            "action_dispatch_dry": "Dispatch Dry Run",
            "action_retry_send": "Retry Send",
            "action_reject": "Reject",
            "label_run_history": "Run History",
            "action_run_scheduled": "Run Scheduled Dry",
            "action_run_forced": "Run Forced Queue",
            "action_refresh_history": "Refresh History",
            "label_event_type": "Event Type",
            "label_status": "Status",
            "activity_status_initial": "History not loaded yet.",
            "activity_empty_initial": "No activity logs yet.",
            "all": "all",
            "audience_senior": "senior",
            "audience_adult": "adult",
            "audience_junior": "junior",
            "status_pending_review": "pending_review",
            "status_approved": "approved",
            "status_sent": "sent",
            "status_rejected": "rejected",
            "status_discarded": "discarded",
            "status_completed": "completed",
            "status_dry_run": "dry_run",
            "status_failed": "failed",
            "status_skipped": "skipped",
            "status_none": "none",
            "recommendation_review": "review",
            "recommendation_special": "special",
            "recommendation_auto_send": "auto_send",
            "recommendation_discard": "discard",
            "tag_low_score": "LOW_SCORE",
            "tag_score_high": "high",
            "tag_score_mid": "mid",
            "tag_score_low": "low",
            "event_scheduled_run": "scheduled_run",
            "event_queue_item": "queue_item",
            "event_review_action": "review_action",
            "event_dispatch": "dispatch",
            "event_dispatch_window": "dispatch_window",
            "event_alert": "alert",
            "item_count": "{count} item(s)",
            "event_count": "{count} event(s)",
            "summary_evening_special": "Evening sends require special items.",
            "summary_evening_normal": "Evening sends follow normal queue rules.",
            "summary_sent_note_dynamic": "Today {sent} / {max}. {rule}",
            "summary_pending_note_dynamic": "Recommendations waiting: review={review}, special={special}.",
            "summary_approved_note_dynamic": "Morning {morning} / Evening {evening}.",
            "summary_weekend_paused": "Today is a weekend. Beta auto-queue is paused; weekday pending review usually lands at {range}.",
            "summary_review_guidance": "Recommended review: {times}.",
            "summary_alert_expectation": "Typical weekday failure alerts: {range}.",
            "summary_load_failed": "Summary load failed: {error}",
            "summary_no_failed_activity": "No failed activity right now.",
            "summary_no_dispatch": "No dispatch activity yet.",
            "queue_loading": "Loading queue...",
            "queue_loaded": "Loaded {count} queue item(s).",
            "queue_load_failed": "Queue load failed: {error}",
            "queue_empty_filtered": "No queue items match the current filter.",
            "queue_not_selected": "No queue item selected.",
            "queue_source_loading": "Queueing source {source}...",
            "queue_source_loaded": "Queued {count} item(s) from {source}.",
            "queue_source_failed": "Queue source failed: {error}",
            "detail_loading": "Loading detail...",
            "detail_load_failed": "Detail load failed: {error}",
            "select_queue_first": "Select a queue item first.",
            "approve_loading": "Approving item...",
            "approve_send_loading": "Approving and sending...",
            "approve_done": "Approved.",
            "approve_send_done": "Approved and dispatched.",
            "approve_failed": "Approve failed: {error}",
            "reject_loading": "Rejecting item...",
            "reject_done": "Rejected.",
            "reject_failed": "Reject failed: {error}",
            "dispatch_loading": "Sending item...",
            "dispatch_dry_loading": "Running dispatch dry run...",
            "dispatch_done": "Sent.",
            "dispatch_dry_done": "Dry run complete.",
            "dispatch_failed": "Dispatch failed: {error}",
            "retry_unavailable": "Retry send is only available for approved or sent items.",
            "activity_loading": "Loading activity history...",
            "activity_loaded": "Loaded {count} activity event(s).",
            "activity_failed": "Activity load failed: {error}",
            "activity_empty": "No activity logs yet.",
            "scheduled_loading": "Running scheduled dry run...",
            "forced_loading": "Running forced queue...",
            "scheduled_done": "Scheduled run complete. Dispatch reason: {reason}.",
            "scheduled_failed": "Scheduled run failed: {error}",
            "queue_id": "queue #{id}",
            "system": "system",
            "score_label": "score {score}",
            "detail_queue_title": "Queue",
            "detail_summary_title": "Summary",
            "detail_teaching_value_title": "Teaching Value",
            "detail_keywords_title": "Keywords",
            "detail_lead_image_title": "Lead Image",
            "detail_reading_passage_title": "Reading Passage",
            "detail_reading_questions_title": "Reading Questions",
            "detail_cloze_answers_title": "Cloze Answers",
            "detail_discussion_points_title": "Discussion Points",
            "detail_traceability_title": "Traceability",
            "detail_exports_title": "Exports",
            "detail_export_teacher": "Teacher HTML",
            "detail_export_student": "Student HTML",
            "detail_export_package": "Package JSON",
            "no_keywords": "No keywords",
            "no_reading_questions": "No reading questions.",
            "no_cloze_items": "No cloze items.",
            "no_discussion_points": "No discussion points.",
            "no_traceability_notes": "No traceability notes.",
            "no_export_links": "No export links yet.",
            "action_view_alert_report": "View Alert Report",
        },
        "zh": {
            "page_title": "教师内容审核台",
            "hero_title": "教师审核台",
            "hero_subtitle": "把新内容拉进审核队列，检查生成后的讲义包，然后直接在页面里批准、拒绝，或发送到钉钉。",
            "hero_export_title": "导出入口",
            "hero_export_hint": "先选择一条队列数据，然后可在这里直接打开最新教师版 HTML。",
            "hero_export_open": "打开教师版 HTML",
            "hero_export_open_disabled": "先选择队列项",
            "language_label": "语言",
            "summary_pending_title": "待审核",
            "summary_pending_note": "等待教师确认。",
            "summary_approved_title": "已批准队列",
            "summary_approved_note": "等待进入下一个发送窗口。",
            "summary_sent_title": "今日已发送",
            "summary_sent_note": "今天的发送节奏会显示在这里。",
            "summary_dispatch_title": "最近派发",
            "summary_dispatch_note": "还没有派发记录。",
            "summary_alerts_title": "告警",
            "summary_alerts_note": "当前没有失败或跳过的记录。",
            "summary_alerts_action": "点击查看完整告警历史。",
            "label_source": "来源",
            "label_audience": "适用人群",
            "label_provider": "模型提供方",
            "label_queue_filter": "队列筛选",
            "label_actions": "操作",
            "action_queue_source": "加入队列",
            "action_refresh_queue": "刷新队列",
            "label_review_queue": "审核队列",
            "queue_status_initial": "队列还没有加载。",
            "queue_empty_initial": "暂时没有队列数据。",
            "label_package_detail": "内容详情",
            "no_selection": "未选择",
            "detail_empty_initial": "选择一条队列内容后，这里会显示生成后的教学材料。",
            "label_reviewer_note": "审核备注",
            "reviewer_note_placeholder": "批准或拒绝前，可以补充一条简短备注。",
            "action_approve": "批准",
            "action_approve_send": "批准并发送",
            "action_dispatch_dry": "派发预演",
            "action_retry_send": "重试发送",
            "action_reject": "拒绝",
            "label_run_history": "运行记录",
            "action_run_scheduled": "执行定时预演",
            "action_run_forced": "强制抓取入队",
            "action_refresh_history": "刷新记录",
            "label_event_type": "事件类型",
            "label_status": "状态",
            "activity_status_initial": "运行记录还没有加载。",
            "activity_empty_initial": "暂时没有运行记录。",
            "all": "全部",
            "audience_senior": "高中",
            "audience_adult": "成人",
            "audience_junior": "初中",
            "status_pending_review": "待审核",
            "status_approved": "已批准",
            "status_sent": "已发送",
            "status_rejected": "已拒绝",
            "status_discarded": "已丢弃",
            "status_completed": "已完成",
            "status_dry_run": "预演",
            "status_failed": "失败",
            "status_skipped": "跳过",
            "status_none": "暂无",
            "recommendation_review": "待审",
            "recommendation_special": "特别推荐",
            "recommendation_auto_send": "自动发送",
            "recommendation_discard": "丢弃",
            "tag_low_score": "低分过滤",
            "tag_score_high": "高分",
            "tag_score_mid": "中分",
            "tag_score_low": "低分",
            "event_scheduled_run": "定时任务",
            "event_queue_item": "入队",
            "event_review_action": "审核动作",
            "event_dispatch": "派发",
            "event_dispatch_window": "发送窗口",
            "event_alert": "告警",
            "item_count": "{count} 条",
            "event_count": "{count} 条记录",
            "summary_evening_special": "晚间自动发送只允许 special 内容。",
            "summary_evening_normal": "晚间自动发送按普通队列规则执行。",
            "summary_sent_note_dynamic": "今日已发送 {sent} / {max}。{rule}",
            "summary_pending_note_dynamic": "待审推荐：review={review}，special={special}。",
            "summary_approved_note_dynamic": "早间 {morning} / 晚间 {evening}。",
            "summary_weekend_paused": "今天是周末，beta 自动抓取暂停；工作日通常会产生 {range} 条待审核内容。",
            "summary_review_guidance": "建议审核时段：{times}。",
            "summary_alert_expectation": "工作日通常会有 {range} 条失败告警。",
            "summary_load_failed": "概要加载失败：{error}",
            "summary_no_failed_activity": "当前没有失败或跳过的记录。",
            "summary_no_dispatch": "还没有派发记录。",
            "queue_loading": "正在加载队列...",
            "queue_loaded": "已加载 {count} 条队列内容。",
            "queue_load_failed": "队列加载失败：{error}",
            "queue_empty_filtered": "当前筛选条件下没有队列内容。",
            "queue_not_selected": "还没有选中队列内容。",
            "queue_source_loading": "正在把来源 {source} 加入队列...",
            "queue_source_loaded": "已从 {source} 加入 {count} 条内容。",
            "queue_source_failed": "加入队列失败：{error}",
            "detail_loading": "正在加载详情...",
            "detail_load_failed": "详情加载失败：{error}",
            "select_queue_first": "请先选择一条队列内容。",
            "approve_loading": "正在批准内容...",
            "approve_send_loading": "正在批准并发送...",
            "approve_done": "已批准。",
            "approve_send_done": "已批准并派发。",
            "approve_failed": "批准失败：{error}",
            "reject_loading": "正在拒绝内容...",
            "reject_done": "已拒绝。",
            "reject_failed": "拒绝失败：{error}",
            "dispatch_loading": "正在发送内容...",
            "dispatch_dry_loading": "正在执行派发预演...",
            "dispatch_done": "已发送。",
            "dispatch_dry_done": "预演完成。",
            "dispatch_failed": "派发失败：{error}",
            "retry_unavailable": "只有已批准或已发送的内容才支持重试发送。",
            "activity_loading": "正在加载运行记录...",
            "activity_loaded": "已加载 {count} 条运行记录。",
            "activity_failed": "运行记录加载失败：{error}",
            "activity_empty": "暂时没有运行记录。",
            "scheduled_loading": "正在执行定时预演...",
            "forced_loading": "正在强制抓取入队...",
            "scheduled_done": "定时任务完成。派发原因：{reason}。",
            "scheduled_failed": "定时任务失败：{error}",
            "queue_id": "队列 #{id}",
            "system": "系统",
            "score_label": "评分 {score}",
            "detail_queue_title": "队列信息",
            "detail_summary_title": "摘要",
            "detail_teaching_value_title": "教学价值",
            "detail_keywords_title": "关键词",
            "detail_lead_image_title": "配图",
            "detail_reading_passage_title": "阅读材料",
            "detail_reading_questions_title": "阅读理解",
            "detail_cloze_answers_title": "完形答案",
            "detail_discussion_points_title": "讨论点",
            "detail_traceability_title": "溯源说明",
            "detail_exports_title": "导出文件",
            "detail_export_teacher": "教师版 HTML",
            "detail_export_student": "学生版 HTML",
            "detail_export_package": "包数据 JSON",
            "no_keywords": "暂无关键词",
            "no_reading_questions": "暂无阅读题。",
            "no_cloze_items": "暂无完形内容。",
            "no_discussion_points": "暂无讨论点。",
            "no_traceability_notes": "暂无溯源说明。",
            "no_export_links": "暂时还没有可访问的导出链接。",
            "action_view_alert_report": "查看详情报告",
        },
    }
    translations_json = json.dumps(translations, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Teacher Content Review</title>
    <style>
      :root {{
        --bg: #f4efe4;
        --panel: rgba(255, 252, 246, 0.92);
        --ink: #172127;
        --muted: #5d686f;
        --line: rgba(23, 33, 39, 0.12);
        --accent: #0f766e;
        --accent-soft: rgba(15, 118, 110, 0.14);
        --warn: #b45309;
        --danger: #b91c1c;
        --shadow: 0 20px 60px rgba(28, 37, 44, 0.12);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        font-family: "Avenir Next", "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(15, 118, 110, 0.18), transparent 35%),
          radial-gradient(circle at right, rgba(180, 83, 9, 0.16), transparent 28%),
          linear-gradient(180deg, #f8f3e8, var(--bg));
      }}
      .shell {{
        width: min(1380px, calc(100vw - 32px));
        margin: 24px auto;
        display: grid;
        gap: 18px;
      }}
      .hero, .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 24px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(14px);
      }}
      .hero {{
        padding: 22px 24px 20px;
      }}
      .hero-top {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 18px;
      }}
      .hero-actions {{
        display: grid;
        gap: 10px;
        min-width: 260px;
      }}
      .hero h1 {{
        margin: 0 0 8px;
        font-size: clamp(1.7rem, 3vw, 2.6rem);
        letter-spacing: -0.04em;
      }}
      .hero p {{
        margin: 0;
        color: var(--muted);
        max-width: 820px;
        line-height: 1.55;
      }}
      .language-field {{
        min-width: 128px;
      }}
      .hero-export-entry {{
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 10px 12px;
        background: rgba(255, 255, 255, 0.72);
      }}
      .hero-export-entry strong {{
        display: block;
        margin-bottom: 6px;
      }}
      .hero-export-entry p {{
        margin: 0 0 8px;
        color: var(--muted);
        font-size: 0.9rem;
      }}
      .hero-link {{
        display: inline-block;
        border-radius: 999px;
        padding: 9px 14px;
        background: var(--accent);
        color: #fff;
        text-decoration: none;
        font-size: 0.9rem;
      }}
      .hero-link.disabled {{
        background: rgba(100, 116, 139, 0.32);
        color: rgba(255, 255, 255, 0.95);
        pointer-events: none;
      }}
      .summary-grid {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 14px;
      }}
      .summary-card {{
        padding: 18px 20px;
      }}
      .summary-card h2 {{
        margin: 0 0 6px;
        font-size: 0.86rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--muted);
      }}
      .summary-card strong {{
        display: block;
        font-size: clamp(1.5rem, 2.4vw, 2.3rem);
        letter-spacing: -0.04em;
      }}
      .summary-card p {{
        margin: 8px 0 0;
        color: var(--muted);
        line-height: 1.5;
        min-height: 42px;
      }}
      .toolbar {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 12px;
        padding: 18px 20px;
      }}
      .field {{
        display: grid;
        gap: 6px;
      }}
      .field label {{
        font-size: 0.82rem;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: var(--muted);
      }}
      select, textarea, button {{
        font: inherit;
      }}
      select, textarea {{
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.9);
        color: var(--ink);
      }}
      select {{
        min-height: 44px;
        padding: 0 12px;
      }}
      textarea {{
        min-height: 110px;
        padding: 12px 14px;
        resize: vertical;
        line-height: 1.45;
      }}
      .toolbar-actions, .detail-actions {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }}
      button {{
        border: 0;
        border-radius: 999px;
        padding: 11px 16px;
        cursor: pointer;
        transition: transform 140ms ease, opacity 140ms ease, background 140ms ease;
      }}
      button:hover {{
        transform: translateY(-1px);
      }}
      button.primary {{
        background: var(--accent);
        color: #fff;
      }}
      button.secondary {{
        background: var(--accent-soft);
        color: var(--accent);
      }}
      button.warn {{
        background: rgba(180, 83, 9, 0.14);
        color: var(--warn);
      }}
      button.danger {{
        background: rgba(185, 28, 28, 0.12);
        color: var(--danger);
      }}
      .layout {{
        display: grid;
        grid-template-columns: 360px minmax(0, 1fr);
        gap: 18px;
      }}
      .panel {{
        overflow: hidden;
      }}
      .queue-panel {{
        display: grid;
        grid-template-rows: auto auto minmax(0, 1fr);
        min-height: 72vh;
      }}
      .panel-head {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 18px 20px 14px;
        border-bottom: 1px solid var(--line);
      }}
      .panel-head h2 {{
        margin: 0;
        font-size: 1rem;
      }}
      .queue-list {{
        display: grid;
        gap: 10px;
        padding: 14px;
        overflow: auto;
      }}
      .queue-item {{
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 14px;
        background: rgba(255, 255, 255, 0.82);
        cursor: pointer;
      }}
      .status-approved {{
        border-color: rgba(15, 118, 110, 0.22);
        background: rgba(233, 248, 246, 0.76);
      }}
      .status-sent {{
        border-color: rgba(37, 99, 235, 0.24);
        background: rgba(239, 246, 255, 0.82);
      }}
      .status-failed {{
        border-color: rgba(185, 28, 28, 0.26);
        background: rgba(254, 242, 242, 0.86);
      }}
      .status-skipped {{
        border-color: rgba(180, 83, 9, 0.22);
        background: rgba(255, 247, 237, 0.86);
      }}
      .queue-item.active {{
        border-color: rgba(15, 118, 110, 0.45);
        box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.18);
        background: rgba(233, 248, 246, 0.88);
      }}
      .queue-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 10px;
      }}
      .pill {{
        border-radius: 999px;
        padding: 5px 9px;
        background: rgba(23, 33, 39, 0.07);
        color: var(--muted);
        font-size: 0.8rem;
      }}
      .pill-status {{
        background: rgba(15, 118, 110, 0.14);
        color: #0f766e;
      }}
      .pill-recommendation {{
        background: rgba(37, 99, 235, 0.12);
        color: #1d4ed8;
      }}
      .pill-score-high {{
        background: rgba(21, 128, 61, 0.12);
        color: #166534;
      }}
      .pill-score-mid {{
        background: rgba(180, 83, 9, 0.14);
        color: #b45309;
      }}
      .pill-score-low {{
        background: rgba(185, 28, 28, 0.12);
        color: #b91c1c;
      }}
      .pill-flag {{
        background: rgba(185, 28, 28, 0.14);
        color: #b91c1c;
        font-weight: 600;
      }}
      .detail-panel {{
        display: grid;
        grid-template-rows: auto auto minmax(0, 1fr);
        min-height: 72vh;
      }}
      .detail-body {{
        padding: 20px;
        overflow: auto;
        display: grid;
        gap: 18px;
      }}
      .detail-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }}
      .card {{
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 16px;
        background: rgba(255, 255, 255, 0.74);
      }}
      .card h3 {{
        margin: 0 0 10px;
        font-size: 0.92rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--muted);
      }}
      .card p, .card li, .card div {{
        line-height: 1.55;
      }}
      .card ul {{
        margin: 0;
        padding-left: 18px;
      }}
      .reading {{
        white-space: pre-wrap;
        line-height: 1.65;
      }}
      .status-bar {{
        padding: 12px 18px;
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-size: 0.92rem;
      }}
      .empty {{
        padding: 26px;
        color: var(--muted);
      }}
      .activity-panel {{
        display: grid;
        grid-template-rows: auto auto minmax(0, 1fr);
        min-height: 34vh;
      }}
      .activity-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        padding: 14px 18px 0;
      }}
      .activity-filters {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 200px));
        gap: 10px;
        padding: 0 18px;
      }}
      .activity-list {{
        display: grid;
        gap: 10px;
        padding: 14px 18px 18px;
        overflow: auto;
      }}
      .activity-item {{
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 14px 16px;
        background: rgba(255, 255, 255, 0.78);
      }}
      .activity-item summary {{
        cursor: pointer;
        list-style: none;
      }}
      .activity-item summary::-webkit-details-marker {{
        display: none;
      }}
      .activity-head {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }}
      .mono {{
        margin-top: 12px;
        padding: 12px;
        border-radius: 14px;
        background: rgba(23, 33, 39, 0.06);
        font-family: "SFMono-Regular", "Menlo", monospace;
        font-size: 0.82rem;
        white-space: pre-wrap;
        word-break: break-word;
      }}
      @media (max-width: 1100px) {{
        .summary-grid {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .toolbar {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .layout {{
          grid-template-columns: 1fr;
        }}
        .hero-top {{
          flex-direction: column;
        }}
        .hero-actions {{
          width: 100%;
          min-width: 0;
        }}
      }}
      @media (max-width: 720px) {{
        .shell {{
          width: min(100vw - 18px, 100%);
          margin: 12px auto 20px;
        }}
        .hero, .panel {{
          border-radius: 18px;
        }}
        .toolbar {{
          grid-template-columns: 1fr;
        }}
        .summary-grid {{
          grid-template-columns: 1fr;
        }}
        .activity-filters {{
          grid-template-columns: 1fr;
        }}
        .detail-grid {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <section class="hero">
        <div class="hero-top">
          <div>
            <h1 id="hero-title" data-i18n="hero_title">Teacher Review Desk</h1>
            <p id="hero-subtitle" data-i18n="hero_subtitle">
              Queue fresh teaching content, inspect the generated worksheet package, then approve,
              reject, or send it to DingTalk without leaving the page.
            </p>
          </div>
          <div class="hero-actions">
            <div class="field language-field">
              <label for="language-select" data-i18n="language_label">Language</label>
              <select id="language-select">
                <option value="en">English</option>
                <option value="zh">中文</option>
              </select>
            </div>
            <div class="hero-export-entry">
              <strong data-i18n="hero_export_title">Export Entry</strong>
              <p data-i18n="hero_export_hint">Select a queue item first, then open the latest teacher HTML directly from here.</p>
              <a id="hero-export-link" class="hero-link disabled" href="#" target="_blank" rel="noreferrer">Select Item To Export</a>
            </div>
          </div>
        </div>
      </section>

      <section class="summary-grid">
        <article class="hero summary-card">
          <h2 data-i18n="summary_pending_title">Pending Review</h2>
          <strong id="summary-pending">0</strong>
          <p id="summary-pending-note" data-i18n="summary_pending_note">Waiting for teacher approval.</p>
        </article>
        <article class="hero summary-card">
          <h2 data-i18n="summary_approved_title">Approved Queue</h2>
          <strong id="summary-approved">0</strong>
          <p id="summary-approved-note" data-i18n="summary_approved_note">Ready for the next send window.</p>
        </article>
        <article class="hero summary-card">
          <h2 data-i18n="summary_sent_title">Sent Today</h2>
          <strong id="summary-sent-today">0</strong>
          <p id="summary-sent-note" data-i18n="summary_sent_note">Daily rhythm stays visible here.</p>
        </article>
        <article class="hero summary-card">
          <h2 data-i18n="summary_dispatch_title">Latest Dispatch</h2>
          <strong id="summary-dispatch-status">none</strong>
          <p id="summary-dispatch-note" data-i18n="summary_dispatch_note">No dispatch activity yet.</p>
        </article>
        <article class="hero summary-card" style="cursor:pointer;" onclick="window.location.href='/alerts'">
          <h2 data-i18n="summary_alerts_title">Alerts</h2>
          <strong id="summary-alerts">0</strong>
          <p id="summary-alerts-note" data-i18n="summary_alerts_note">No failed activity right now.</p>
        </article>
      </section>

      <section class="panel toolbar">
        <div class="field">
          <label for="source" data-i18n="label_source">Source</label>
          <select id="source">{source_options}</select>
        </div>
        <div class="field">
          <label for="audience" data-i18n="label_audience">Audience</label>
          <select id="audience">
            <option value="senior" data-i18n="audience_senior">senior</option>
            <option value="adult" data-i18n="audience_adult">adult</option>
            <option value="junior" data-i18n="audience_junior">junior</option>
          </select>
        </div>
        <div class="field">
          <label for="provider" data-i18n="label_provider">Provider</label>
          <select id="provider">{provider_options}</select>
        </div>
        <div class="field">
          <label for="status-filter" data-i18n="label_queue_filter">Queue Filter</label>
          <select id="status-filter">
            <option value="" data-i18n="all">all</option>
            <option value="pending_review" data-i18n="status_pending_review">pending_review</option>
            <option value="approved" data-i18n="status_approved">approved</option>
            <option value="sent" data-i18n="status_sent">sent</option>
            <option value="rejected" data-i18n="status_rejected">rejected</option>
            <option value="discarded" data-i18n="status_discarded">discarded</option>
          </select>
        </div>
        <div class="field">
          <label data-i18n="label_actions">Actions</label>
          <div class="toolbar-actions">
            <button class="primary" id="queue-source-button" data-i18n="action_queue_source">Queue Source</button>
            <button class="secondary" id="refresh-queue-button" data-i18n="action_refresh_queue">Refresh Queue</button>
          </div>
        </div>
      </section>

      <section class="layout">
        <div class="panel queue-panel">
          <div class="panel-head">
            <h2 data-i18n="label_review_queue">Review Queue</h2>
            <span id="queue-count" class="pill">0 item(s)</span>
          </div>
          <div class="status-bar" id="queue-status" data-i18n="queue_status_initial">Queue not loaded yet.</div>
          <div class="queue-list" id="queue-list">
            <div class="empty" data-i18n="queue_empty_initial">No queue data yet.</div>
          </div>
        </div>

        <div class="panel detail-panel">
          <div class="panel-head">
            <h2 data-i18n="label_package_detail">Package Detail</h2>
            <span id="detail-status-pill" class="pill" data-i18n="no_selection">no selection</span>
          </div>
          <div class="detail-body" id="detail-body">
            <div class="empty" data-i18n="detail_empty_initial">Select a queue item to inspect the generated material.</div>
          </div>
          <div class="status-bar">
            <div class="field">
              <label for="review-note" data-i18n="label_reviewer_note">Reviewer Note</label>
              <textarea id="review-note" data-i18n-placeholder="reviewer_note_placeholder" placeholder="Add a short reviewer note before approving or rejecting."></textarea>
            </div>
            <div class="detail-actions" style="margin-top: 12px;">
              <button class="secondary" id="approve-button" data-i18n="action_approve">Approve</button>
              <button class="primary" id="approve-send-button" data-i18n="action_approve_send">Approve + Send</button>
              <button class="warn" id="dry-dispatch-button" data-i18n="action_dispatch_dry">Dispatch Dry Run</button>
              <button class="warn" id="retry-send-button" data-i18n="action_retry_send">Retry Send</button>
              <button class="danger" id="reject-button" data-i18n="action_reject">Reject</button>
            </div>
          </div>
        </div>
      </section>

      <section class="panel activity-panel">
        <div class="panel-head">
          <h2 data-i18n="label_run_history">Run History</h2>
          <span id="activity-count" class="pill">0 event(s)</span>
        </div>
        <div class="activity-actions">
          <button class="secondary" id="run-scheduled-button" data-i18n="action_run_scheduled">Run Scheduled Dry</button>
          <button class="warn" id="run-force-sources-button" data-i18n="action_run_forced">Run Forced Queue</button>
          <button class="secondary" id="refresh-activity-button" data-i18n="action_refresh_history">Refresh History</button>
        </div>
        <div class="activity-filters">
          <div class="field">
            <label for="activity-event-filter" data-i18n="label_event_type">Event Type</label>
            <select id="activity-event-filter">
              <option value="" data-i18n="all">all</option>
              <option value="scheduled_run" data-i18n="event_scheduled_run">scheduled_run</option>
              <option value="queue_item" data-i18n="event_queue_item">queue_item</option>
              <option value="review_action" data-i18n="event_review_action">review_action</option>
              <option value="dispatch" data-i18n="event_dispatch">dispatch</option>
              <option value="dispatch_window" data-i18n="event_dispatch_window">dispatch_window</option>
              <option value="alert" data-i18n="event_alert">alert</option>
            </select>
          </div>
          <div class="field">
            <label for="activity-status-filter" data-i18n="label_status">Status</label>
            <select id="activity-status-filter">
              <option value="" data-i18n="all">all</option>
              <option value="completed" data-i18n="status_completed">completed</option>
              <option value="approved" data-i18n="status_approved">approved</option>
              <option value="rejected" data-i18n="status_rejected">rejected</option>
              <option value="pending_review" data-i18n="status_pending_review">pending_review</option>
              <option value="dry_run" data-i18n="status_dry_run">dry_run</option>
              <option value="sent" data-i18n="status_sent">sent</option>
              <option value="failed" data-i18n="status_failed">failed</option>
              <option value="skipped" data-i18n="status_skipped">skipped</option>
            </select>
          </div>
        </div>
        <div class="status-bar" id="activity-status" data-i18n="activity_status_initial">History not loaded yet.</div>
        <div class="activity-list" id="activity-list">
          <div class="empty" data-i18n="activity_empty_initial">No activity logs yet.</div>
        </div>
      </section>
    </div>

    <script>
      const translations = {translations_json};

      function getInitialLanguage() {{
        const saved = window.localStorage.getItem("reviewDeskLanguage");
        if (saved && translations[saved]) {{
          return saved;
        }}
        return navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
      }}

      const state = {{
        language: getInitialLanguage(),
        selectedQueueId: null,
        selectedQueue: null,
        queueItems: [],
        activityItems: [],
      }};

      const languageSelect = document.getElementById("language-select");
      const sourceSelect = document.getElementById("source");
      const audienceSelect = document.getElementById("audience");
      const providerSelect = document.getElementById("provider");
      const queueListEl = document.getElementById("queue-list");
      const queueCountEl = document.getElementById("queue-count");
      const queueStatusEl = document.getElementById("queue-status");
      const detailBodyEl = document.getElementById("detail-body");
      const detailStatusPillEl = document.getElementById("detail-status-pill");
      const reviewNoteEl = document.getElementById("review-note");
      const statusFilterEl = document.getElementById("status-filter");
      const activityListEl = document.getElementById("activity-list");
      const activityCountEl = document.getElementById("activity-count");
      const activityStatusEl = document.getElementById("activity-status");
      const activityEventFilterEl = document.getElementById("activity-event-filter");
      const activityStatusFilterEl = document.getElementById("activity-status-filter");
      const heroExportLinkEl = document.getElementById("hero-export-link");

      languageSelect.value = state.language;
      sourceSelect.value = {json.dumps(normalized_default)};
      audienceSelect.value = "senior";
      providerSelect.value = "router";

      languageSelect.addEventListener("change", () => setLanguage(languageSelect.value));
      document.getElementById("queue-source-button").addEventListener("click", queueSource);
      document.getElementById("refresh-queue-button").addEventListener("click", loadQueue);
      document.getElementById("approve-button").addEventListener("click", () => approveSelected(false));
      document.getElementById("approve-send-button").addEventListener("click", () => approveSelected(true));
      document.getElementById("dry-dispatch-button").addEventListener("click", () => dispatchSelected(false, true));
      document.getElementById("retry-send-button").addEventListener("click", retrySend);
      document.getElementById("reject-button").addEventListener("click", rejectSelected);
      document.getElementById("run-scheduled-button").addEventListener("click", () => runScheduled(false));
      document.getElementById("run-force-sources-button").addEventListener("click", () => runScheduled(true));
      document.getElementById("refresh-activity-button").addEventListener("click", loadActivity);
      statusFilterEl.addEventListener("change", loadQueue);
      activityEventFilterEl.addEventListener("change", loadActivity);
      activityStatusFilterEl.addEventListener("change", loadActivity);

      async function fetchJson(url, options = undefined) {{
        const response = await fetch(url, options);
        if (!response.ok) {{
          let detail = `${{response.status}} ${{response.statusText}}`;
          try {{
            const data = await response.json();
            if (data && data.detail) {{
              detail = data.detail;
            }}
          }} catch (error) {{
            // ignore JSON parse errors
          }}
          throw new Error(detail);
        }}
        return response.json();
      }}

      function t(key, params = undefined) {{
        const locale = translations[state.language] || translations.en;
        const fallback = translations.en || {{}};
        let template = locale[key] || fallback[key] || key;
        if (!params) {{
          return template;
        }}
        return template.replace(/\{{(\w+)\}}/g, (_, token) => String(params[token] ?? ""));
      }}

      function statusLabel(status) {{
        const key = `status_${{String(status || "none")}}`;
        return translations[state.language]?.[key] || translations.en?.[key] || String(status || "none");
      }}

      function recommendationLabel(value) {{
        const key = `recommendation_${{String(value || "")}}`;
        return translations[state.language]?.[key] || translations.en?.[key] || String(value || "");
      }}

      function eventLabel(value) {{
        const key = `event_${{String(value || "")}}`;
        return translations[state.language]?.[key] || translations.en?.[key] || String(value || "");
      }}

      function scoreTagClass(score) {{
        const value = Number(score || 0);
        if (value >= 86) return "pill-score-high";
        if (value >= 78) return "pill-score-mid";
        return "pill-score-low";
      }}

      function scoreTagLabel(score) {{
        const value = Number(score || 0);
        if (value >= 86) return t("tag_score_high");
        if (value >= 78) return t("tag_score_mid");
        return t("tag_score_low");
      }}

      function applyStaticTranslations() {{
        document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
        document.title = t("page_title");
        document.querySelectorAll("[data-i18n]").forEach((node) => {{
          const key = node.getAttribute("data-i18n");
          node.textContent = t(key);
        }});
        document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {{
          const key = node.getAttribute("data-i18n-placeholder");
          node.setAttribute("placeholder", t(key));
        }});
        if (!state.queueItems.length) {{
          queueCountEl.textContent = t("item_count", {{ count: 0 }});
        }}
        if (!state.activityItems.length) {{
          activityCountEl.textContent = t("event_count", {{ count: 0 }});
        }}
        updateHeroExportLink((state.selectedQueue?.export_urls || {{}}).teacher_html || null);
      }}

      function refreshLanguage() {{
        applyStaticTranslations();
        if (state.queueItems.length) {{
          renderQueue(state.queueItems);
        }} else {{
          queueListEl.innerHTML = `<div class="empty">${{escapeHtml(t("queue_empty_initial"))}}</div>`;
          setDetailPlaceholder(t("detail_empty_initial"));
        }}
        if (state.activityItems.length) {{
          renderActivity(state.activityItems);
        }} else {{
          activityListEl.innerHTML = `<div class="empty">${{escapeHtml(t("activity_empty_initial"))}}</div>`;
        }}
        if (state.selectedQueueId) {{
          loadDetail(state.selectedQueueId);
        }}
        loadSummary();
      }}

      function setLanguage(language) {{
        state.language = translations[language] ? language : "en";
        languageSelect.value = state.language;
        window.localStorage.setItem("reviewDeskLanguage", state.language);
        refreshLanguage();
      }}

      function setQueueStatus(message) {{
        queueStatusEl.textContent = message;
      }}

      function setActivityStatus(message) {{
        activityStatusEl.textContent = message;
      }}

      function statusClass(status) {{
        switch (String(status || "")) {{
          case "approved":
            return "status-approved";
          case "sent":
            return "status-sent";
          case "failed":
            return "status-failed";
          case "skipped":
            return "status-skipped";
          default:
            return "";
        }}
      }}

      async function loadSummary() {{
        try {{
          const summary = await fetchJson("/api/dashboard-summary");
          const queueCounts = summary.queue_counts || {{}};
          const betaOps = summary.beta_ops || {{}};
          const summaryNow = summary.now ? new Date(summary.now) : null;
          const isWeekend = summaryNow ? [0, 6].includes(summaryNow.getDay()) : false;
          document.getElementById("summary-pending").textContent = String(queueCounts.pending_review || 0);
          document.getElementById("summary-approved").textContent = String(queueCounts.approved || 0);
          document.getElementById("summary-sent-today").textContent = String(summary.sent_today || 0);
          document.getElementById("summary-alerts").textContent = String((summary.failed_activity_count || 0) + (summary.skipped_activity_count || 0));
          const latestDispatch = summary.latest_dispatch || summary.latest_dispatch_window || summary.latest_activity;
          const latestStatus = latestDispatch?.status || "none";
          const latestMessage = latestDispatch?.message || t("summary_no_dispatch");
          document.getElementById("summary-dispatch-status").textContent = statusLabel(latestStatus);
          document.getElementById("summary-dispatch-note").textContent = String(latestMessage);
          const eveningRule = summary.schedule?.evening_requires_special ? t("summary_evening_special") : t("summary_evening_normal");
          document.getElementById("summary-sent-note").textContent = t("summary_sent_note_dynamic", {{
            sent: summary.sent_today || 0,
            max: summary.schedule?.max_daily_push || 0,
            rule: eveningRule,
          }});
          const pendingRange = betaOps.expected_pending_review_per_weekday || "2-5";
          if (summary.schedule?.weekend_auto_queue_enabled === false && isWeekend && !queueCounts.pending_review && !queueCounts.approved) {{
            document.getElementById("summary-pending-note").textContent = t("summary_weekend_paused", {{ range: pendingRange }});
          }} else {{
            document.getElementById("summary-pending-note").textContent = t("summary_pending_note_dynamic", {{
              review: summary.recommendation_counts?.review || 0,
              special: summary.recommendation_counts?.special || 0,
            }});
          }}
          const reviewTimes = Array.isArray(betaOps.recommended_review_times)
            ? betaOps.recommended_review_times.join(" / ")
            : "";
          const approvedNote = t("summary_approved_note_dynamic", {{
            morning: summary.schedule?.morning_send_time || "--",
            evening: summary.schedule?.evening_send_time || "--",
          }});
          document.getElementById("summary-approved-note").textContent =
            reviewTimes ? `${{approvedNote}} ${{t("summary_review_guidance", {{ times: reviewTimes }})}}` : approvedNote;
           const alertCount = (summary.failed_activity_count || 0) + (summary.skipped_activity_count || 0);
           document.getElementById("summary-alerts-note").textContent =
             alertCount > 0 ? t("summary_alerts_action") : t("summary_no_failed_activity");
        }} catch (error) {{
          const message = t("summary_load_failed", {{ error: error.message }});
          document.getElementById("summary-dispatch-note").textContent = message;
          document.getElementById("summary-alerts-note").textContent = message;
        }}
      }}

      function setDetailPlaceholder(message) {{
        state.selectedQueue = null;
        detailStatusPillEl.textContent = t("no_selection");
        detailBodyEl.innerHTML = `<div class="empty">${{escapeHtml(message)}}</div>`;
        updateHeroExportLink(null);
      }}

      function updateHeroExportLink(url) {{
        if (!heroExportLinkEl) {{
          return;
        }}
        if (url) {{
          heroExportLinkEl.href = url;
          heroExportLinkEl.classList.remove("disabled");
          heroExportLinkEl.textContent = t("hero_export_open");
          return;
        }}
        heroExportLinkEl.href = "#";
        heroExportLinkEl.classList.add("disabled");
        heroExportLinkEl.textContent = t("hero_export_open_disabled");
      }}

      function escapeHtml(value) {{
        return String(value || "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;");
      }}

      function renderQueue(items) {{
        state.queueItems = items;
        queueCountEl.textContent = t("item_count", {{ count: items.length }});
        if (!items.length) {{
          queueListEl.innerHTML = `<div class="empty">${{escapeHtml(t("queue_empty_filtered"))}}</div>`;
          setDetailPlaceholder(t("queue_not_selected"));
          return;
        }}
        queueListEl.innerHTML = items.map((entry) => {{
          const item = entry.queue;
          const active = item.queue_id === state.selectedQueueId ? "active" : "";
          const tone = statusClass(item.status);
          return `
            <article class="queue-item ${{active}} ${{tone}}" data-queue-id="${{item.queue_id}}">
              <strong>${{escapeHtml(item.optimized_title)}}</strong>
              <div class="queue-meta">
                <span class="pill ${{scoreTagClass(item.score_total)}}">${{escapeHtml(t("score_label", {{ score: item.score_total }}))}}</span>
                <span class="pill ${{scoreTagClass(item.score_total)}}">${{escapeHtml(scoreTagLabel(item.score_total))}}</span>
                <span class="pill pill-recommendation">${{escapeHtml(recommendationLabel(item.review_recommendation))}}</span>
                <span class="pill pill-status">${{escapeHtml(statusLabel(item.status))}}</span>
              </div>
              <div class="queue-meta">
                <span class="pill">${{escapeHtml(item.source_name)}}</span>
                <span class="pill">${{escapeHtml(item.audience)}}</span>
              </div>
            </article>
          `;
        }}).join("");
        queueListEl.querySelectorAll("[data-queue-id]").forEach((node) => {{
          node.addEventListener("click", () => loadDetail(Number(node.dataset.queueId)));
        }});
      }}

      function renderActivity(items) {{
        state.activityItems = items;
        activityCountEl.textContent = t("event_count", {{ count: items.length }});
        if (!items.length) {{
          activityListEl.innerHTML = `<div class="empty">${{escapeHtml(t("activity_empty"))}}</div>`;
          return;
        }}
        activityListEl.innerHTML = items.map((entry) => {{
          const item = entry.activity;
          const tone = statusClass(item.status);
          const isAlert = item.event_type === "alert";
          const detailFile = item.payload?.detail_filename;
          const itemTitle = isAlert ? `Alert: ${{item.source_name || t("system")}}` : item.message;
          const alertLink = isAlert && detailFile
            ? `<div style="margin-top:10px;"><a href="/alerts/${{detailFile}}" target="_blank" style="color:var(--accent);font-weight:600;">🔗 ${{t("action_view_alert_report")}}</a></div>`
            : "";
          const lowScoreTag = item.status === "skipped" && item.payload?.reason === "low_score"
            ? `<span class="pill pill-flag">${{escapeHtml(t("tag_low_score"))}}</span>`
            : "";
          const lowScoreDetail = item.status === "skipped" && item.payload?.reason === "low_score"
            ? `<div class="queue-meta"><span class="pill ${{scoreTagClass(item.payload?.score_total)}}">${{escapeHtml(t("score_label", {{ score: item.payload?.score_total }}))}}</span><span class="pill">${{escapeHtml("min " + String(item.payload?.queue_review_score_min ?? ""))}}</span></div>`
            : "";
          const payload = (!isAlert && item.payload && Object.keys(item.payload).length)
            ? `<div class="mono">${{escapeHtml(JSON.stringify(item.payload, null, 2))}}</div>`
            : "";
          return `
            <details class="activity-item ${{tone}}">
              <summary>
                <div class="activity-head">
                  <strong>${{escapeHtml(itemTitle)}}</strong>
                  <span class="pill pill-status">${{escapeHtml(statusLabel(item.status))}}</span>
                </div>
                <div class="queue-meta">
                  <span class="pill">${{escapeHtml(eventLabel(item.event_type))}}</span>
                  <span class="pill">${{escapeHtml(item.source_name || t("system"))}}</span>
                  <span class="pill">${{escapeHtml(item.created_at || "")}}</span>
                  ${{lowScoreTag}}
                </div>
              </summary>
              ${{alertLink}}
              ${{lowScoreDetail}}
              ${{payload}}
            </details>
          `;
        }}).join("");
      }}

      async function loadQueue() {{
        const status = statusFilterEl.value;
        const query = new URLSearchParams();
        if (status) {{
          query.set("status", status);
        }}
        query.set("limit", "50");
        setQueueStatus(t("queue_loading"));
        try {{
          const items = await fetchJson(`/api/review-queue?${{query.toString()}}`);
          renderQueue(items);
          setQueueStatus(t("queue_loaded", {{ count: items.length }}));
          if (!state.selectedQueueId && items.length) {{
            await loadDetail(items[0].queue.queue_id);
          }}
        }} catch (error) {{
          setQueueStatus(t("queue_load_failed", {{ error: error.message }}));
        }}
      }}

      async function loadActivity() {{
        const eventType = activityEventFilterEl.value;
        const status = activityStatusFilterEl.value;
        const query = new URLSearchParams({{ limit: "30" }});
        if (eventType) {{
          query.set("event_type", eventType);
        }}
        if (status) {{
          query.set("status", status);
        }}
        setActivityStatus(t("activity_loading"));
        try {{
          const items = await fetchJson(`/api/activity-log?${{query.toString()}}`);
          renderActivity(items);
          setActivityStatus(t("activity_loaded", {{ count: items.length }}));
        }} catch (error) {{
          setActivityStatus(t("activity_failed", {{ error: error.message }}));
        }}
      }}

      async function loadDetail(queueId) {{
        state.selectedQueueId = queueId;
        renderQueue(state.queueItems);
        detailStatusPillEl.textContent = t("queue_id", {{ id: queueId }});
        detailBodyEl.innerHTML = `<div class="empty">${{escapeHtml(t("detail_loading"))}}</div>`;
        try {{
          const detail = await fetchJson(`/api/review-queue/${{queueId}}`);
          state.selectedQueue = detail.queue;
          state.selectedQueue.export_urls = detail.export_urls || {{}};
          reviewNoteEl.value = detail.queue.reviewer_note || "";
          detailStatusPillEl.textContent = `${{statusLabel(detail.queue.status)}} / ${{recommendationLabel(detail.queue.review_recommendation)}}`;
          detailBodyEl.innerHTML = renderDetail(detail);
          updateHeroExportLink((detail.export_urls || {{}}).teacher_html || null);
        }} catch (error) {{
          setDetailPlaceholder(t("detail_load_failed", {{ error: error.message }}));
        }}
      }}

      function renderDetail(detail) {{
        const queue = detail.queue;
        const generated = detail.generated;
        const preview = generated.preview;
        const pkg = generated.package;
        const exportUrls = detail.export_urls || {{}};
        const questions = (pkg.reading_questions || []).map((item) => `<li>${{escapeHtml(item.stem)}} <strong>${{escapeHtml(item.answer)}}</strong></li>`).join("");
        const clozeQuestions = (pkg.cloze_questions || []).map((item) => `<li>${{escapeHtml(item.question_id)}} <strong>${{escapeHtml(item.answer)}}</strong></li>`).join("");
        const keywords = (pkg.keywords || []).map((item) => `<span class="pill">${{escapeHtml(item)}}</span>`).join("");
        const traceability = (pkg.traceability_notes || []).map((item) => `<li>${{escapeHtml(item)}}</li>`).join("");
        const discussion = (pkg.discussion_points || []).map((item) => `<li>${{escapeHtml(item)}}</li>`).join("");
        const exportLinks = [
          exportUrls.teacher_html
            ? `<li><a href="${{escapeHtml(exportUrls.teacher_html)}}" target="_blank" rel="noreferrer">${{escapeHtml(t("detail_export_teacher"))}}</a></li>`
            : "",
          exportUrls.student_html
            ? `<li><a href="${{escapeHtml(exportUrls.student_html)}}" target="_blank" rel="noreferrer">${{escapeHtml(t("detail_export_student"))}}</a></li>`
            : "",
          exportUrls.package_json
            ? `<li><a href="${{escapeHtml(exportUrls.package_json)}}" target="_blank" rel="noreferrer">${{escapeHtml(t("detail_export_package"))}}</a></li>`
            : "",
        ].filter(Boolean).join("");
        const image = preview.article.lead_image_url
          ? `<div class="card"><h3>${{escapeHtml(t("detail_lead_image_title"))}}</h3><img alt="cover" src="${{escapeHtml(preview.article.lead_image_url)}}" style="width:100%;border-radius:14px;display:block;" /></div>`
          : "";
        return `
          <div class="detail-grid">
            <div class="card">
              <h3>${{escapeHtml(t("detail_queue_title"))}}</h3>
              <div><strong>${{escapeHtml(queue.optimized_title)}}</strong></div>
              <div class="queue-meta" style="margin-top:12px;">
                <span class="pill ${{scoreTagClass(queue.score_total)}}">${{escapeHtml(t("score_label", {{ score: queue.score_total }}))}}</span>
                <span class="pill ${{scoreTagClass(queue.score_total)}}">${{escapeHtml(scoreTagLabel(queue.score_total))}}</span>
                <span class="pill pill-status">${{escapeHtml(statusLabel(queue.status))}}</span>
                <span class="pill pill-recommendation">${{escapeHtml(recommendationLabel(queue.review_recommendation))}}</span>
                <span class="pill">${{escapeHtml(queue.source_name)}}</span>
              </div>
            </div>
            <div class="card">
              <h3>${{escapeHtml(t("detail_summary_title"))}}</h3>
              <p>${{escapeHtml(pkg.summary)}}</p>
            </div>
            <div class="card">
              <h3>${{escapeHtml(t("detail_teaching_value_title"))}}</h3>
              <p>${{escapeHtml(pkg.teaching_value)}}</p>
            </div>
            <div class="card">
              <h3>${{escapeHtml(t("detail_keywords_title"))}}</h3>
              <div class="queue-meta">${{keywords || `<span class="pill">${{escapeHtml(t("no_keywords"))}}</span>`}}</div>
            </div>
          </div>
          ${{image}}
          <div class="card">
            <h3>${{escapeHtml(t("detail_reading_passage_title"))}}</h3>
            <div class="reading">${{escapeHtml(pkg.reading_passage)}}</div>
          </div>
          <div class="detail-grid">
            <div class="card">
              <h3>${{escapeHtml(t("detail_reading_questions_title"))}}</h3>
              <ul>${{questions || `<li>${{escapeHtml(t("no_reading_questions"))}}</li>`}}</ul>
            </div>
            <div class="card">
              <h3>${{escapeHtml(t("detail_cloze_answers_title"))}}</h3>
              <ul>${{clozeQuestions || `<li>${{escapeHtml(t("no_cloze_items"))}}</li>`}}</ul>
            </div>
            <div class="card">
              <h3>${{escapeHtml(t("detail_discussion_points_title"))}}</h3>
              <ul>${{discussion || `<li>${{escapeHtml(t("no_discussion_points"))}}</li>`}}</ul>
            </div>
            <div class="card">
              <h3>${{escapeHtml(t("detail_traceability_title"))}}</h3>
              <ul>${{traceability || `<li>${{escapeHtml(t("no_traceability_notes"))}}</li>`}}</ul>
            </div>
            <div class="card">
              <h3>${{escapeHtml(t("detail_exports_title"))}}</h3>
              <ul>${{exportLinks || `<li>${{escapeHtml(t("no_export_links"))}}</li>`}}</ul>
            </div>
          </div>
        `;
      }}

      async function queueSource() {{
        const sourceName = sourceSelect.value;
        const audience = audienceSelect.value;
        const provider = providerSelect.value;
        const query = new URLSearchParams({{
          audience,
          provider,
          limit: "1",
        }});
        setQueueStatus(t("queue_source_loading", {{ source: sourceName }}));
        try {{
          const items = await fetchJson(`/api/queue/${{encodeURIComponent(sourceName)}}?${{query.toString()}}`, {{
            method: "POST",
          }});
          setQueueStatus(t("queue_source_loaded", {{ count: items.length, source: sourceName }}));
          await loadQueue();
          await loadSummary();
          await loadActivity();
          if (items.length) {{
            await loadDetail(items[0].queue.queue_id);
          }}
        }} catch (error) {{
          setQueueStatus(t("queue_source_failed", {{ error: error.message }}));
        }}
      }}

      async function approveSelected(send) {{
        if (!state.selectedQueueId) {{
          setQueueStatus(t("select_queue_first"));
          return;
        }}
        const note = reviewNoteEl.value.trim();
        setQueueStatus(send ? t("approve_send_loading") : t("approve_loading"));
        try {{
          await fetchJson(`/api/review-queue/${{state.selectedQueueId}}/approve`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ note, send }}),
          }});
          await loadQueue();
          await loadDetail(state.selectedQueueId);
          await loadSummary();
          await loadActivity();
          setQueueStatus(send ? t("approve_send_done") : t("approve_done"));
        }} catch (error) {{
          setQueueStatus(t("approve_failed", {{ error: error.message }}));
        }}
      }}

      async function rejectSelected() {{
        if (!state.selectedQueueId) {{
          setQueueStatus(t("select_queue_first"));
          return;
        }}
        const note = reviewNoteEl.value.trim();
        setQueueStatus(t("reject_loading"));
        try {{
          await fetchJson(`/api/review-queue/${{state.selectedQueueId}}/reject`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ note }}),
          }});
          await loadQueue();
          await loadDetail(state.selectedQueueId);
          await loadSummary();
          await loadActivity();
          setQueueStatus(t("reject_done"));
        }} catch (error) {{
          setQueueStatus(t("reject_failed", {{ error: error.message }}));
        }}
      }}

      async function dispatchSelected(send, force = false) {{
        if (!state.selectedQueueId) {{
          setQueueStatus(t("select_queue_first"));
          return;
        }}
        setQueueStatus(send ? t("dispatch_loading") : t("dispatch_dry_loading"));
        try {{
          await fetchJson(`/api/review-queue/${{state.selectedQueueId}}/dispatch`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ send, force }}),
          }});
          await loadQueue();
          await loadDetail(state.selectedQueueId);
          await loadSummary();
          await loadActivity();
          setQueueStatus(send ? t("dispatch_done") : t("dispatch_dry_done"));
        }} catch (error) {{
          setQueueStatus(t("dispatch_failed", {{ error: error.message }}));
        }}
      }}

      async function retrySend() {{
        if (!state.selectedQueueId || !state.selectedQueue) {{
          setQueueStatus(t("select_queue_first"));
          return;
        }}
        if (!["approved", "sent"].includes(state.selectedQueue.status)) {{
          setQueueStatus(t("retry_unavailable"));
          return;
        }}
        await dispatchSelected(true, true);
      }}

      async function runScheduled(forceSources) {{
        const payload = {{
          audience: audienceSelect.value,
          provider: providerSelect.value,
          force_sources: forceSources,
          send: false,
          force_dispatch: false,
          max_dispatch_items: 1,
        }};
        setActivityStatus(forceSources ? t("forced_loading") : t("scheduled_loading"));
        try {{
          const result = await fetchJson("/api/scheduled/run", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify(payload),
          }});
          await loadQueue();
          await loadSummary();
          await loadActivity();
          const dispatchReason = result.dispatch?.decision?.reason || "ok";
          setActivityStatus(t("scheduled_done", {{ reason: dispatchReason }}));
        }} catch (error) {{
          setActivityStatus(t("scheduled_failed", {{ error: error.message }}));
        }}
      }}

      applyStaticTranslations();
      loadSummary();
      loadQueue();
      loadActivity();
    </script>
  </body>
</html>
"""
