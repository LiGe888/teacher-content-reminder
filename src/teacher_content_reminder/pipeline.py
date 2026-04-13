from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

from teacher_content_reminder.alerting import AlertService
from teacher_content_reminder.config import AppConfig, load_config
from teacher_content_reminder.delivery import (
    DingTalkBotClient,
    WeChatOfficialClient,
    WeComBotClient,
    render_dingtalk_markdown,
    render_wechat_template_fields,
    render_wecom_markdown,
)
from teacher_content_reminder.exporters import ExportService
from teacher_content_reminder.extractors import HTMLArticleExtractor
from teacher_content_reminder.fetchers import get_fetcher
from teacher_content_reminder.generation import GenerationService
from teacher_content_reminder.llm.factory import build_provider_client
from teacher_content_reminder.models import ActivityLogEntry, GeneratedPreviewItem, PreviewItem, ReviewQueueItem
from teacher_content_reminder.repository import SQLiteRepository
from teacher_content_reminder.scheduler import (
    dispatch_decision,
    due_source_names,
    initial_queue_status,
    local_now,
    review_recommendation,
)
from teacher_content_reminder.scoring import score_article
from teacher_content_reminder.utils import hash_text


class ContentPipeline:
    def __init__(self, config_path: str | Path | None = None, db_path: str | Path | None = None) -> None:
        self.config: AppConfig = load_config(config_path)
        self.repository = SQLiteRepository(db_path)
        self.extractor = HTMLArticleExtractor()
        self.generation = GenerationService(self.config)
        self.alerting = AlertService(
            config=self.config.alerting,
            repository=self.repository,
            timezone_name=self.config.project.timezone,
        )

    def initialize(self) -> None:
        self.repository.initialize()

    def list_sources(self) -> list[str]:
        return [source.name for source in self.config.enabled_sources]

    def preview_source(self, source_name: str, limit: int = 3, persist: bool = False) -> list[PreviewItem]:
        source = self.config.get_source(source_name)
        fetcher = get_fetcher(source.type)
        # Pull a wider candidate window so scheduled runs are not starved by
        # duplicates or low-quality links occupying the top positions.
        candidates = fetcher.fetch(source, limit=max(limit * 10, 20))

        items: list[PreviewItem] = []
        for candidate in candidates:
            if self.repository.has_article(candidate.url):
                continue

            article = self.extractor.extract(
                url=candidate.url,
                source_name=candidate.source_name,
                source_category=candidate.source_category,
            )
            if candidate.title and not article.title:
                article.title = candidate.title

            # Secondary dedup: skip if same content body already exists under a different URL
            if article.raw_text and self.repository.has_article(candidate.url, content_hash=hash_text(article.raw_text)):
                continue

            score = score_article(article)
            preview = PreviewItem(candidate=candidate, article=article, score=score)
            if persist:
                self.repository.save_article(article, score)
            items.append(preview)
            if len(items) >= limit:
                break
        return items

    def fetch_all(self, limit_per_source: int = 3, persist: bool = True) -> dict[str, list[PreviewItem]]:
        results: dict[str, list[PreviewItem]] = {}
        for source in self.config.enabled_sources:
            results[source.name] = self.preview_source(source.name, limit=limit_per_source, persist=persist)
        return results

    def generate_preview_source(
        self,
        source_name: str,
        audience: str | None = None,
        exercise_profile: str | None = None,
        provider: str | None = None,
        limit: int = 1,
        persist: bool = False,
    ) -> list[GeneratedPreviewItem]:
        audience_key = audience or self.config.generation.default_audience
        exercise_profile_name = exercise_profile or self.config.generation.default_exercise_profile
        previews = self.preview_source(source_name=source_name, limit=limit, persist=persist)
        generation_service = (
            GenerationService(self.config, client=build_provider_client(self.config, provider, require_enabled=False))
            if provider
            else self.generation
        )

        results: list[GeneratedPreviewItem] = []
        for preview in previews:
            package = generation_service.generate(
                article=preview.article,
                audience_key=audience_key,
                exercise_profile_name=exercise_profile_name,
            )
            if persist:
                if not self.repository.has_article(preview.article.canonical_url):
                    self.repository.save_article(preview.article, preview.score)
                package.package_id = self.repository.save_generated_package(preview.article, package)
            results.append(GeneratedPreviewItem(preview=preview, package=package))
        return results

    def queue_source_for_review(
        self,
        source_name: str,
        audience: str | None = None,
        exercise_profile: str | None = None,
        provider: str | None = None,
        limit: int | None = None,
    ) -> list[ReviewQueueItem]:
        queue_limit = limit or self.config.review.limit_per_source
        generated_items = self.generate_preview_source(
            source_name=source_name,
            audience=audience,
            exercise_profile=exercise_profile,
            provider=provider,
            limit=queue_limit,
            persist=True,
        )

        queued_items: list[ReviewQueueItem] = []
        for item in generated_items:
            recommendation = review_recommendation(self.config, item.preview.score.total_score)
            if recommendation == "discard":
                self._log_activity(
                    event_type="queue_item",
                    status="skipped",
                    message=(
                        f"Skipped low-score item for {source_name}: "
                        f"{item.package.optimized_title}"
                    ),
                    source_name=source_name,
                    payload={
                        "reason": "low_score",
                        "score_total": item.preview.score.total_score,
                        "queue_review_score_min": self.config.selection.queue_review_score_min,
                        "title": item.package.optimized_title,
                        "article_url": item.preview.article.canonical_url,
                    },
                )
                continue
            status = initial_queue_status(self.config, recommendation)
            queue_id = self.repository.enqueue_review_item(
                item,
                recommendation=recommendation,
                status=status,
            )
            queued_item = self.repository.get_review_queue_item(queue_id)
            if queued_item is not None:
                self._log_activity(
                    event_type="queue_item",
                    status=queued_item.status,
                    message=f"Queued {queued_item.optimized_title}",
                    source_name=queued_item.source_name,
                    queue_id=queued_item.queue_id,
                    package_id=queued_item.package_id,
                    payload={
                        "recommendation": queued_item.review_recommendation,
                        "score_total": queued_item.score_total,
                    },
                )
                queued_items.append(queued_item)
        return queued_items

    def queue_due_sources(
        self,
        now: datetime | None = None,
        audience: str | None = None,
        exercise_profile: str | None = None,
        provider: str | None = None,
        limit_per_source: int | None = None,
        source_names: list[str] | None = None,
        force: bool = False,
    ) -> dict[str, list[ReviewQueueItem]]:
        current = now or local_now(self.config.project.timezone)
        targets = source_names or due_source_names(self.config, current=current, force=force)
        results: dict[str, list[ReviewQueueItem]] = {}
        for source_name in targets:
            # Content-mix guard: skip if this category is already over its quota
            if not force and not self._category_quota_ok(source_name):
                self._log_activity(
                    event_type="queue_item",
                    status="skipped",
                    message=f"Skipped {source_name}: category quota reached per content_mix config.",
                    source_name=source_name,
                )
                results[source_name] = []
                continue
            try:
                results[source_name] = self.queue_source_for_review(
                    source_name=source_name,
                    audience=audience,
                    exercise_profile=exercise_profile,
                    provider=provider,
                    limit=limit_per_source,
                )
            except Exception as exc:
                results[source_name] = []
                self._log_activity(
                    event_type="queue_item",
                    status="failed",
                    message=f"Queue failed for {source_name}: {exc}",
                    source_name=source_name,
                    payload={
                        "exception_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
                if self.config.alerting.notify_source_failure:
                    self._send_alert(
                        category="source_failure",
                        severity="warning",
                        title=f"[{self.config.project.name}] Source queue failed",
                        message=f"Source {source_name} failed during scheduled queueing.",
                        fingerprint=f"source_failure:{source_name}:{type(exc).__name__}",
                        source_name=source_name,
                        payload={
                            "exception_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
        return results

    def _category_quota_ok(self, source_name: str) -> bool:
        """Return True if queueing from source_name would not exceed the content_mix quota.

        Only enforced when selection.content_mix is configured.  The check looks at
        the last 20 pending/approved items in the review queue and compares the
        category share against the configured ratio.
        """
        content_mix = self.config.selection.content_mix
        if not content_mix:
            return True
        source = self.config.sources.get(source_name)
        if source is None:
            return True
        category = source.category
        target_ratio = content_mix.get(category)
        if target_ratio is None:
            return True  # category not in mix config — always allow

        recent_items = self.repository.list_review_queue(limit=20)
        if not recent_items:
            return True

        # Count how many of the recent items belong to this category
        category_counts: dict[str, int] = {}
        for item in recent_items:
            src = self.config.sources.get(item.source_name)
            cat = src.category if src else "unknown"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        total = len(recent_items)
        current_ratio = category_counts.get(category, 0) / total
        # Allow up to 1.5× the target ratio as a soft ceiling
        return current_ratio < target_ratio * 1.5

    def list_review_queue(
        self,
        status: str | None = None,
        recommendation: str | None = None,
        limit: int = 50,
    ) -> list[ReviewQueueItem]:
        return self.repository.list_review_queue(status=status, recommendation=recommendation, limit=limit)

    def list_activity_logs(
        self,
        event_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ActivityLogEntry]:
        return self.repository.list_activity_logs(event_type=event_type, status=status, limit=limit)

    def get_dashboard_summary(self, now: datetime | None = None) -> dict[str, object]:
        current = now or local_now(self.config.project.timezone)
        queue_counts = self.repository.count_review_queue_by_status()
        recommendation_counts = self.repository.count_review_queue_by_recommendation()
        latest_activity = self.repository.list_activity_logs(limit=1)
        latest_dispatch = self.repository.list_activity_logs(event_type="dispatch", limit=1)
        latest_dispatch_window = self.repository.list_activity_logs(event_type="dispatch_window", limit=1)
        latest_failed_activity = self.repository.list_activity_logs(status="failed", limit=1)
        latest_skipped_activity = self.repository.list_activity_logs(status="skipped", limit=1)
        return {
            "now": current,
            "queue_counts": queue_counts,
            "recommendation_counts": recommendation_counts,
            "sent_today": self.repository.count_delivery_events_for_date(
                channel=self.config.delivery.channel,
                local_date=current.date().isoformat(),
                timezone_name=self.config.project.timezone,
            ),
            "failed_activity_count": self.repository.count_activity_logs(status="failed"),
            "skipped_activity_count": self.repository.count_activity_logs(status="skipped"),
            "latest_activity": latest_activity[0] if latest_activity else None,
            "latest_dispatch": latest_dispatch[0] if latest_dispatch else None,
            "latest_dispatch_window": latest_dispatch_window[0] if latest_dispatch_window else None,
            "latest_failed_activity": latest_failed_activity[0] if latest_failed_activity else None,
            "latest_skipped_activity": latest_skipped_activity[0] if latest_skipped_activity else None,
            "schedule": {
                "weekday_only": self.config.schedule.weekday_only,
                "weekend_auto_queue_enabled": self.config.schedule.weekend_auto_queue_enabled,
                "weekend_send_enabled": self.config.schedule.weekend_send_enabled,
                "morning_send_time": self.config.schedule.morning_send_time,
                "evening_send_time": self.config.schedule.evening_send_time,
                "evening_requires_special": self.config.schedule.evening_requires_special,
                "max_daily_push": self.config.project.max_daily_push,
            },
            "beta_ops": {
                "auto_queue_sources": [
                    source.name for source in self.config.enabled_sources if source.auto_queue_enabled
                ],
                "manual_only_sources": [
                    source.name for source in self.config.enabled_sources if not source.auto_queue_enabled
                ],
                "recommended_review_times": ["07:50-08:20", "12:10-12:30", "16:30-17:00"],
                "expected_pending_review_per_weekday": "2-5",
                "expected_failure_alerts_per_weekday": "0-2",
            },
        }

    def get_review_queue_detail(self, queue_id: int) -> dict[str, object]:
        queue_item = self.repository.get_review_queue_item(queue_id)
        if queue_item is None:
            raise KeyError(f"Unknown review queue item: {queue_id}")
        generated = self.repository.load_generated_preview_by_queue_id(queue_id)
        return {
            "queue_item": queue_item,
            "generated": generated,
        }

    def approve_review_item(
        self,
        queue_id: int,
        reviewer_note: str = "",
        send: bool = False,
        export_dir: str = ".exports",
        export_formats: tuple[str, ...] = ("markdown", "html", "json", "pdf"),
    ) -> dict[str, object]:
        item = self.repository.get_review_queue_item(queue_id)
        if item is None:
            raise KeyError(f"Unknown review queue item: {queue_id}")
        self.repository.update_review_status(queue_id, "approved", reviewer_note=reviewer_note or item.reviewer_note)
        self._log_activity(
            event_type="review_action",
            status="approved",
            message=f"Approved {item.optimized_title}",
            source_name=item.source_name,
            queue_id=item.queue_id,
            package_id=item.package_id,
            payload={"reviewer_note": reviewer_note or item.reviewer_note},
        )
        if not send:
            refreshed = self.repository.get_review_queue_item(queue_id)
            return {
                "queue_item": refreshed,
                "dispatched": False,
            }
        return self.dispatch_queue_item(
            queue_id,
            send=True,
            export_dir=export_dir,
            export_formats=export_formats,
            force=True,
        )

    def reject_review_item(self, queue_id: int, reviewer_note: str = "") -> ReviewQueueItem:
        item = self.repository.get_review_queue_item(queue_id)
        if item is None:
            raise KeyError(f"Unknown review queue item: {queue_id}")
        self.repository.update_review_status(queue_id, "rejected", reviewer_note=reviewer_note or item.reviewer_note)
        self._log_activity(
            event_type="review_action",
            status="rejected",
            message=f"Rejected {item.optimized_title}",
            source_name=item.source_name,
            queue_id=item.queue_id,
            package_id=item.package_id,
            payload={"reviewer_note": reviewer_note or item.reviewer_note},
        )
        refreshed = self.repository.get_review_queue_item(queue_id)
        if refreshed is None:
            raise KeyError(f"Unknown review queue item: {queue_id}")
        return refreshed

    def dispatch_queue_item(
        self,
        queue_id: int,
        send: bool = False,
        export_dir: str = ".exports",
        export_formats: tuple[str, ...] = ("markdown", "html", "json", "pdf"),
        force: bool = False,
    ) -> dict[str, object]:
        queue_item = self.repository.get_review_queue_item(queue_id)
        if queue_item is None:
            raise KeyError(f"Unknown review queue item: {queue_id}")
        if queue_item.status not in {"approved", "sent"} and not force:
            raise ValueError(f"Queue item {queue_id} is not approved for dispatch.")

        preview = self.repository.load_generated_preview_by_queue_id(queue_id)
        export = ExportService(export_dir).export_generated_preview(preview, formats=export_formats)
        title, markdown = render_dingtalk_markdown(preview)
        response: dict[str, object]
        delivery_status = "dry_run"
        channels = self._delivery_channels()
        if send:
            channel_results: dict[str, dict[str, object]] = {}
            for channel in channels:
                try:
                    channel_response = self._send_via_channel(channel, preview, title, markdown)
                    channel_results[channel] = channel_response
                except Exception as exc:
                    channel_results[channel] = {
                        "error": str(exc),
                        "exception_type": type(exc).__name__,
                    }
            failed_channels = [
                channel
                for channel, result in channel_results.items()
                if not self._is_channel_success(channel, result)
            ]
            delivery_status = "failed" if failed_channels else "sent"
            response = {
                "channels": channel_results,
                "failed_channels": failed_channels,
            }
        else:
            response = {"dry_run": True, "channels": channels}

        channel_payloads = response.get("channels", {}) if isinstance(response.get("channels"), dict) else {}
        for channel in channels:
            self.repository.record_delivery_event(
                channel=channel,
                status=delivery_status,
                response_payload=channel_payloads.get(channel, response),
                queue_id=queue_id,
                package_id=preview.package.package_id,
            )
        self._log_activity(
            event_type="dispatch",
            status=delivery_status,
            message=f"{delivery_status} {queue_item.optimized_title}",
            source_name=queue_item.source_name,
            queue_id=queue_id,
            package_id=preview.package.package_id,
            payload={
                "send": send,
                "force": force,
                "response": response,
                "export_directory": export.get("directory"),
            },
        )
        if send and delivery_status == "failed" and self.config.alerting.notify_dispatch_failure:
            self._send_alert(
                category="dispatch_failure",
                severity="critical",
                title=f"[{self.config.project.name}] Dispatch failed",
                message=f"Failed to send {queue_item.optimized_title} to configured channels.",
                fingerprint=f"dispatch_failure:{queue_item.queue_id}",
                source_name=queue_item.source_name,
                queue_id=queue_item.queue_id,
                package_id=preview.package.package_id,
                payload={
                    "response": response,
                    "title": queue_item.optimized_title,
                },
            )

        if delivery_status == "sent":
            self.repository.update_review_status(
                queue_id,
                "sent",
                reviewer_note=queue_item.reviewer_note,
                export_directory=str(export.get("directory", "")),
                dingtalk_response=response,
            )
        else:
            self.repository.update_review_status(
                queue_id,
                queue_item.status,
                reviewer_note=queue_item.reviewer_note,
                export_directory=str(export.get("directory", "")),
                dingtalk_response=response,
            )

        refreshed = self.repository.get_review_queue_item(queue_id)
        return {
            "queue_item": refreshed,
            "title": title,
            "markdown": markdown,
            "response": response,
            "delivery_status": delivery_status,
            "export": export,
        }

    def dispatch_approved_items(
        self,
        now: datetime | None = None,
        send: bool = False,
        force: bool = False,
        max_items: int = 1,
        export_dir: str = ".exports",
        export_formats: tuple[str, ...] = ("markdown", "html", "json", "pdf"),
    ) -> dict[str, object]:
        current = now or local_now(self.config.project.timezone)
        primary_channel = self._delivery_channels()[0]
        sent_today = self.repository.count_delivery_events_for_date(
            channel=primary_channel,
            local_date=current.date().isoformat(),
            timezone_name=self.config.project.timezone,
        )
        last_sent = self.repository.get_last_delivery_event(primary_channel, status="sent")
        decision = dispatch_decision(
            self.config,
            now=current,
            sent_today_count=sent_today,
            last_event=last_sent,
            force=force,
        )
        if not decision.allowed:
            self._log_activity(
                event_type="dispatch_window",
                status="skipped",
                message=f"Dispatch skipped: {decision.reason}",
                payload={
                    "slot": decision.slot,
                    "sent_today": sent_today,
                },
            )
            return {
                "decision": {
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "slot": decision.slot,
                },
                "sent_today": sent_today,
                "items": [],
            }

        queue_items = sorted(
            self.repository.list_review_queue(status="approved", limit=100),
            key=_dispatch_priority,
        )
        if (
            not force
            and decision.slot == "evening"
            and self.config.schedule.evening_requires_special
        ):
            queue_items = [item for item in queue_items if item.review_recommendation == "special"]
            if not queue_items:
                self._log_activity(
                    event_type="dispatch_window",
                    status="skipped",
                    message="Evening dispatch skipped: no special items.",
                    payload={
                        "slot": decision.slot,
                        "sent_today": sent_today,
                    },
                )
                return {
                    "decision": {
                        "allowed": False,
                        "reason": "no_evening_special_items",
                        "slot": decision.slot,
                    },
                    "sent_today": sent_today,
                    "items": [],
                }
        dispatch_limit = max_items if force else min(max_items, 1)
        dispatched: list[dict[str, object]] = []
        for item in queue_items[:dispatch_limit]:
            dispatched.append(
                self.dispatch_queue_item(
                    item.queue_id,
                    send=send,
                    export_dir=export_dir,
                    export_formats=export_formats,
                    force=True,
                )
            )

        return {
            "decision": {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "slot": decision.slot,
            },
            "sent_today": sent_today,
            "items": dispatched,
        }

    def run_scheduled(
        self,
        now: datetime | None = None,
        audience: str | None = None,
        exercise_profile: str | None = None,
        provider: str | None = None,
        limit_per_source: int | None = None,
        source_names: list[str] | None = None,
        force_sources: bool = False,
        send: bool = False,
        force_dispatch: bool = False,
        max_dispatch_items: int = 1,
        export_dir: str = ".exports",
        export_formats: tuple[str, ...] = ("markdown", "html", "json", "pdf"),
    ) -> dict[str, object]:
        current = now or local_now(self.config.project.timezone)
        try:
            queued = self.queue_due_sources(
                now=current,
                audience=audience,
                exercise_profile=exercise_profile,
                provider=provider,
                limit_per_source=limit_per_source,
                source_names=source_names,
                force=force_sources,
            )
            dispatch = self.dispatch_approved_items(
                now=current,
                send=send,
                force=force_dispatch,
                max_items=max_dispatch_items,
                export_dir=export_dir,
                export_formats=export_formats,
            )
            queued_count = sum(len(items) for items in queued.values())
            dispatched_count = len(dispatch.get("items", []))
            self._log_activity(
                event_type="scheduled_run",
                status="completed",
                message=f"Scheduled run queued {queued_count} item(s), dispatched {dispatched_count}.",
                payload={
                    "now": current.isoformat(),
                    "queued_count": queued_count,
                    "dispatch_reason": dispatch.get("decision", {}).get("reason"),
                    "dispatch_slot": dispatch.get("decision", {}).get("slot"),
                    "sent_today": dispatch.get("sent_today"),
                    "sources": list(queued.keys()),
                },
            )
            return {
                "now": current,
                "queued": queued,
                "dispatch": dispatch,
            }
        except Exception as exc:
            self._log_activity(
                event_type="scheduled_run",
                status="failed",
                message=f"Scheduled run failed: {exc}",
                payload={
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "now": current.isoformat(),
                },
            )
            if self.config.alerting.notify_scheduled_failure:
                self._send_alert(
                    category="scheduled_run_failure",
                    severity="critical",
                    title=f"[{self.config.project.name}] Scheduled run failed",
                    message="The scheduled pipeline run exited with an exception.",
                    fingerprint=f"scheduled_run_failure:{type(exc).__name__}",
                    payload={
                        "exception_type": type(exc).__name__,
                        "error": str(exc),
                        "now": current.isoformat(),
                    },
                )
            raise

    def _build_dingtalk_client(self) -> DingTalkBotClient:
        webhook_url = os.getenv(self.config.delivery.webhook_env, "")
        if not webhook_url:
            raise ValueError(f"Missing env {self.config.delivery.webhook_env}")
        secret = (
            os.getenv(self.config.delivery.secret_env or "", "")
            if self.config.delivery.secret_env
            else None
        )
        return DingTalkBotClient(webhook_url=webhook_url, secret=secret)

    def _build_wecom_client(self) -> WeComBotClient:
        webhook_url = os.getenv("WECOM_WEBHOOK_URL", "").strip()
        if not webhook_url:
            raise ValueError("Missing env WECOM_WEBHOOK_URL")
        return WeComBotClient(webhook_url=webhook_url)

    def _build_wechat_official_client(self) -> WeChatOfficialClient:
        appid = os.getenv("WECHAT_OFFICIAL_APPID", "").strip()
        appsecret = os.getenv("WECHAT_OFFICIAL_APPSECRET", "").strip()
        template_id = os.getenv("WECHAT_OFFICIAL_TEMPLATE_ID", "").strip()
        if not appid:
            raise ValueError("Missing env WECHAT_OFFICIAL_APPID")
        if not appsecret:
            raise ValueError("Missing env WECHAT_OFFICIAL_APPSECRET")
        if not template_id:
            raise ValueError("Missing env WECHAT_OFFICIAL_TEMPLATE_ID")
        return WeChatOfficialClient(
            appid=appid,
            appsecret=appsecret,
            template_id=template_id,
        )

    def _delivery_channels(self) -> list[str]:
        raw = self.config.delivery.channel or "dingtalk"
        channels = [item.strip().lower() for item in raw.split(",") if item.strip()]
        return channels or ["dingtalk"]

    def _send_via_channel(
        self,
        channel: str,
        preview: GeneratedPreviewItem,
        title: str,
        markdown: str,
    ) -> dict[str, object]:
        if channel == "dingtalk":
            client = self._build_dingtalk_client()
            return client.send_markdown(title=title, text=markdown)
        if channel == "wecom":
            client = self._build_wecom_client()
            content = render_wecom_markdown(preview)
            return client.send_markdown(content=content)
        if channel == "wechat_official":
            client = self._build_wechat_official_client()
            fields = render_wechat_template_fields(preview)
            touser_env = os.getenv("WECHAT_OFFICIAL_TOUSER", "").strip()
            if not touser_env:
                raise ValueError("Missing env WECHAT_OFFICIAL_TOUSER")
            users = [item.strip() for item in touser_env.split(",") if item.strip()]
            results: dict[str, object] = {}
            for user in users:
                results[user] = client.send_template_message(
                    touser=user,
                    title=fields["title"],
                    summary=fields["summary"],
                    source_name=fields["source_name"],
                    score_text=fields["score_text"],
                    url=fields["article_url"],
                )
            return {"results": results}
        raise ValueError(f"Unsupported delivery channel: {channel}")

    def _is_channel_success(self, channel: str, response: dict[str, object]) -> bool:
        if "error" in response:
            return False
        if channel in {"dingtalk", "wecom"}:
            return response.get("errcode") == 0
        if channel == "wechat_official":
            results = response.get("results", {})
            if not isinstance(results, dict) or not results:
                return False
            return all(
                isinstance(payload, dict) and payload.get("errcode") == 0
                for payload in results.values()
            )
        return False

    def _log_activity(
        self,
        event_type: str,
        status: str,
        message: str,
        source_name: str = "",
        queue_id: int | None = None,
        package_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.repository.record_activity_log(
            event_type=event_type,
            status=status,
            message=message,
            source_name=source_name,
            queue_id=queue_id,
            package_id=package_id,
            payload=payload,
        )

    def send_test_alert(
        self,
        title: str = "Teacher Content Reminder alert test",
        message: str = "Manual alert smoke test from the deployment checklist.",
        severity: str = "info",
    ) -> dict[str, object]:
        return self._send_alert(
            category="manual_test",
            severity=severity,
            title=title,
            message=message,
            fingerprint=f"manual_test:{severity}:{title}",
            payload={"manual": True},
            force=True,
        )

    def send_command_failure_alert(self, command_name: str, exc: Exception) -> dict[str, object]:
        return self._send_alert(
            category="command_failure",
            severity="critical",
            title=f"[{self.config.project.name}] Command failed",
            message=f"CLI command `{command_name}` failed with {type(exc).__name__}.",
            fingerprint=f"command_failure:{command_name}:{type(exc).__name__}",
            payload={
                "command_name": command_name,
                "exception_type": type(exc).__name__,
                "error": str(exc),
            },
            force=True,
        )

    def _send_alert(
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
        return self.alerting.send_alert(
            category=category,
            severity=severity,
            title=title,
            message=message,
            fingerprint=fingerprint,
            source_name=source_name,
            queue_id=queue_id,
            package_id=package_id,
            payload=payload,
            force=force,
        )


def _dispatch_priority(item: ReviewQueueItem) -> tuple[int, float, str]:
    recommendation_rank = {
        "special": 0,
        "auto_send": 1,
        "review": 2,
        "discard": 3,
    }
    created_at = item.created_at.isoformat() if item.created_at else ""
    return (
        recommendation_rank.get(item.review_recommendation, 9),
        -item.score_total,
        created_at,
    )
