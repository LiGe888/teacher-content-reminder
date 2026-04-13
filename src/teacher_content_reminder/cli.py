from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import sys

from teacher_content_reminder.config import default_config_path
from teacher_content_reminder.delivery import DingTalkBotClient, render_dingtalk_markdown
from teacher_content_reminder.diagnostics import build_beta_report, build_runtime_report
from teacher_content_reminder.exporters import ExportService
from teacher_content_reminder.llm.factory import build_llm_client, build_provider_client
from teacher_content_reminder.llm.smoke_test import run_smoke_test
from teacher_content_reminder.models import GeneratedPreviewItem, PreviewItem, ReviewQueueItem
from teacher_content_reminder.pipeline import ContentPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="teacher-content-reminder")
    parser.add_argument("--config", default=str(default_config_path()))
    parser.add_argument("--db-path", default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")

    beta_parser = subparsers.add_parser("beta-check")
    beta_parser.add_argument("--live", action="store_true")
    beta_parser.add_argument("--json", action="store_true")

    smoke_parser = subparsers.add_parser("llm-smoke-test")
    smoke_parser.add_argument("--provider", default=None)
    smoke_parser.add_argument("--json", action="store_true")

    alert_parser = subparsers.add_parser("alert-smoke-test")
    alert_parser.add_argument("--title", default="Teacher Content Reminder alert test")
    alert_parser.add_argument("--message", default="Manual alert smoke test from the deployment checklist.")
    alert_parser.add_argument("--severity", default="info")
    alert_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("init-db")
    subparsers.add_parser("list-sources")

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("--source", required=True)
    preview_parser.add_argument("--limit", type=int, default=3)
    preview_parser.add_argument("--persist", action="store_true")
    preview_parser.add_argument("--json", action="store_true")

    fetch_all_parser = subparsers.add_parser("fetch-all")
    fetch_all_parser.add_argument("--limit", type=int, default=2)
    fetch_all_parser.add_argument("--persist", action="store_true")

    generate_parser = subparsers.add_parser("generate-preview")
    generate_parser.add_argument("--source", required=True)
    generate_parser.add_argument("--audience", choices=("junior", "senior", "adult"), default=None)
    generate_parser.add_argument("--exercise-profile", default=None)
    generate_parser.add_argument("--provider", default=None)
    generate_parser.add_argument("--limit", type=int, default=1)
    generate_parser.add_argument("--persist", action="store_true")
    generate_parser.add_argument("--export-dir", default=None)
    generate_parser.add_argument("--export-formats", default="markdown,html,json,pdf")
    generate_parser.add_argument("--json", action="store_true")

    export_parser = subparsers.add_parser("export-preview")
    export_parser.add_argument("--source", required=True)
    export_parser.add_argument("--audience", choices=("junior", "senior", "adult"), default=None)
    export_parser.add_argument("--exercise-profile", default=None)
    export_parser.add_argument("--provider", default=None)
    export_parser.add_argument("--limit", type=int, default=1)
    export_parser.add_argument("--persist", action="store_true")
    export_parser.add_argument("--output-dir", default=".exports")
    export_parser.add_argument("--formats", default="markdown,html,json,pdf")
    export_parser.add_argument("--json", action="store_true")

    queue_parser = subparsers.add_parser("queue-source")
    queue_parser.add_argument("--source", required=True)
    queue_parser.add_argument("--audience", choices=("junior", "senior", "adult"), default=None)
    queue_parser.add_argument("--exercise-profile", default=None)
    queue_parser.add_argument("--provider", default=None)
    queue_parser.add_argument("--limit", type=int, default=None)
    queue_parser.add_argument("--json", action="store_true")

    review_queue_parser = subparsers.add_parser("review-queue")
    review_queue_parser.add_argument("--status", default=None)
    review_queue_parser.add_argument("--recommendation", default=None)
    review_queue_parser.add_argument("--limit", type=int, default=20)
    review_queue_parser.add_argument("--json", action="store_true")

    approve_parser = subparsers.add_parser("review-approve")
    approve_parser.add_argument("--queue-id", type=int, required=True)
    approve_parser.add_argument("--note", default="")
    approve_parser.add_argument("--send", action="store_true")
    approve_parser.add_argument("--export-dir", default=".exports")
    approve_parser.add_argument("--export-formats", default="markdown,html,json,pdf")
    approve_parser.add_argument("--json", action="store_true")

    reject_parser = subparsers.add_parser("review-reject")
    reject_parser.add_argument("--queue-id", type=int, required=True)
    reject_parser.add_argument("--note", default="")
    reject_parser.add_argument("--json", action="store_true")

    dispatch_parser = subparsers.add_parser("dispatch-approved")
    dispatch_parser.add_argument("--send", action="store_true")
    dispatch_parser.add_argument("--force", action="store_true")
    dispatch_parser.add_argument("--max-items", type=int, default=1)
    dispatch_parser.add_argument("--now", default=None)
    dispatch_parser.add_argument("--export-dir", default=".exports")
    dispatch_parser.add_argument("--export-formats", default="markdown,html,json,pdf")
    dispatch_parser.add_argument("--json", action="store_true")

    scheduled_parser = subparsers.add_parser("run-scheduled")
    scheduled_parser.add_argument("--source", action="append", default=None)
    scheduled_parser.add_argument("--audience", choices=("junior", "senior", "adult"), default=None)
    scheduled_parser.add_argument("--exercise-profile", default=None)
    scheduled_parser.add_argument("--provider", default=None)
    scheduled_parser.add_argument("--limit-per-source", type=int, default=None)
    scheduled_parser.add_argument("--max-dispatch-items", type=int, default=1)
    scheduled_parser.add_argument("--send", action="store_true")
    scheduled_parser.add_argument("--force-sources", action="store_true")
    scheduled_parser.add_argument("--force-dispatch", action="store_true")
    scheduled_parser.add_argument("--now", default=None)
    scheduled_parser.add_argument("--export-dir", default=".exports")
    scheduled_parser.add_argument("--export-formats", default="markdown,html,json,pdf")
    scheduled_parser.add_argument("--json", action="store_true")

    send_parser = subparsers.add_parser("send-preview")
    send_parser.add_argument("--source", required=True)
    send_parser.add_argument("--audience", choices=("junior", "senior", "adult"), default=None)
    send_parser.add_argument("--exercise-profile", default=None)
    send_parser.add_argument("--provider", default=None)
    send_parser.add_argument("--limit", type=int, default=1)
    send_parser.add_argument("--persist", action="store_true")
    send_parser.add_argument("--export-dir", default=".exports")
    send_parser.add_argument("--export-formats", default="markdown,html,json,pdf")
    send_parser.add_argument("--send", action="store_true")
    send_parser.add_argument("--allow-low-score", action="store_true")
    send_parser.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pipeline = ContentPipeline(config_path=Path(args.config), db_path=args.db_path)

    if args.command == "init-db":
        pipeline.initialize()
        print(f"Initialized database at {pipeline.repository.db_path}")
        return 0

    if args.command == "doctor":
        report = build_runtime_report(pipeline.config)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_doctor_report(report))
        return 0

    if args.command == "beta-check":
        report = build_beta_report(pipeline.config, live=args.live)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_beta_report(report))
        return 0

    if args.command == "llm-smoke-test":
        try:
            client = (
                build_provider_client(pipeline.config, args.provider, require_enabled=False)
                if args.provider
                else build_llm_client(pipeline.config)
            )
            payload = run_smoke_test(client)
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"LLM smoke test failed: {exc}", file=sys.stderr)
            return 1
        report = {
            "provider": client.provider,
            "model": client.model,
            "response": payload,
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_smoke_report(report))
        return 0

    if args.command == "alert-smoke-test":
        pipeline.initialize()
        try:
            result = pipeline.send_test_alert(
                title=args.title,
                message=args.message,
                severity=args.severity,
            )
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Alert smoke test failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(_serialize_for_json(result), ensure_ascii=False, indent=2))
        else:
            print(f"alert_status: {result.get('status')}")
            print(f"sent: {result.get('sent')}")
            if "response" in result:
                print(f"response: {result['response']}")
        return 0

    if args.command == "list-sources":
        for source in pipeline.config.enabled_sources:
            print(f"- {source.name} ({source.type}, {source.category}) -> {source.entry_url}")
        return 0

    if args.command == "preview":
        pipeline.initialize()
        try:
            items = pipeline.preview_source(args.source, limit=args.limit, persist=args.persist)
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Preview failed: {exc}", file=sys.stderr)
            pipeline.send_command_failure_alert("preview", exc)
            return 1
        if args.json:
            payload = [preview_to_dict(item) for item in items]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for index, item in enumerate(items, start=1):
                print(format_preview(item, index=index))
        return 0

    if args.command == "fetch-all":
        pipeline.initialize()
        try:
            results = pipeline.fetch_all(limit_per_source=args.limit, persist=args.persist)
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Fetch failed: {exc}", file=sys.stderr)
            pipeline.send_command_failure_alert("fetch-all", exc)
            return 1
        for source_name, items in results.items():
            print(f"{source_name}: {len(items)} item(s)")
        return 0

    if args.command == "generate-preview":
        pipeline.initialize()
        try:
            items = pipeline.generate_preview_source(
                source_name=args.source,
                audience=args.audience,
                exercise_profile=args.exercise_profile,
                provider=args.provider,
                limit=args.limit,
                persist=args.persist,
            )
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Generate failed: {exc}", file=sys.stderr)
            pipeline.send_command_failure_alert("generate-preview", exc)
            return 1
        export_results = _maybe_export_items(items, output_dir=args.export_dir, formats=args.export_formats)
        if args.json:
            payload = [
                generated_preview_to_dict(item, export=export_results[index] if export_results else None)
                for index, item in enumerate(items)
            ]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for index, item in enumerate(items, start=1):
                print(
                    format_generated_preview(
                        item,
                        index=index,
                        export=export_results[index - 1] if export_results else None,
                    )
                )
        return 0

    if args.command == "export-preview":
        pipeline.initialize()
        try:
            items = pipeline.generate_preview_source(
                source_name=args.source,
                audience=args.audience,
                exercise_profile=args.exercise_profile,
                provider=args.provider,
                limit=args.limit,
                persist=args.persist,
            )
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Export failed during generation: {exc}", file=sys.stderr)
            return 1
        export_results = _export_items(items, output_dir=args.output_dir, formats=args.formats)
        if args.json:
            payload = [
                generated_preview_to_dict(item, export=export_results[index])
                for index, item in enumerate(items)
            ]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for index, item in enumerate(items, start=1):
                print(format_generated_preview(item, index=index, export=export_results[index - 1]))
        return 0

    if args.command == "queue-source":
        pipeline.initialize()
        try:
            items = pipeline.queue_source_for_review(
                source_name=args.source,
                audience=args.audience,
                exercise_profile=args.exercise_profile,
                provider=args.provider,
                limit=args.limit,
            )
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Queue failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps([review_queue_item_to_dict(item) for item in items], ensure_ascii=False, indent=2))
        else:
            for index, item in enumerate(items, start=1):
                print(format_review_queue_item(item, index=index))
        return 0

    if args.command == "review-queue":
        pipeline.initialize()
        items = pipeline.list_review_queue(
            status=args.status,
            recommendation=args.recommendation,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps([review_queue_item_to_dict(item) for item in items], ensure_ascii=False, indent=2))
        else:
            for index, item in enumerate(items, start=1):
                print(format_review_queue_item(item, index=index))
        return 0

    if args.command == "review-approve":
        pipeline.initialize()
        try:
            result = pipeline.approve_review_item(
                queue_id=args.queue_id,
                reviewer_note=args.note,
                send=args.send,
                export_dir=args.export_dir,
                export_formats=_parse_export_formats(args.export_formats),
            )
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Approve failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(_serialize_for_json(_approval_result_to_dict(result)), ensure_ascii=False, indent=2))
        else:
            print(format_approval_result(result))
        return 0

    if args.command == "review-reject":
        pipeline.initialize()
        try:
            item = pipeline.reject_review_item(queue_id=args.queue_id, reviewer_note=args.note)
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Reject failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(review_queue_item_to_dict(item), ensure_ascii=False, indent=2))
        else:
            print(format_review_queue_item(item, index=1))
        return 0

    if args.command == "dispatch-approved":
        pipeline.initialize()
        try:
            result = pipeline.dispatch_approved_items(
                now=_parse_now_argument(args.now),
                send=args.send,
                force=args.force,
                max_items=args.max_items,
                export_dir=args.export_dir,
                export_formats=_parse_export_formats(args.export_formats),
            )
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Dispatch failed: {exc}", file=sys.stderr)
            pipeline.send_command_failure_alert("dispatch-approved", exc)
            return 1
        if args.json:
            print(json.dumps(_serialize_for_json(_dispatch_result_to_dict(result)), ensure_ascii=False, indent=2))
        else:
            print(format_dispatch_result(result))
        return 0

    if args.command == "run-scheduled":
        pipeline.initialize()
        try:
            result = pipeline.run_scheduled(
                now=_parse_now_argument(args.now),
                audience=args.audience,
                exercise_profile=args.exercise_profile,
                provider=args.provider,
                limit_per_source=args.limit_per_source,
                source_names=args.source,
                force_sources=args.force_sources,
                send=args.send,
                force_dispatch=args.force_dispatch,
                max_dispatch_items=args.max_dispatch_items,
                export_dir=args.export_dir,
                export_formats=_parse_export_formats(args.export_formats),
            )
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Scheduled run failed: {exc}", file=sys.stderr)
            pipeline.send_command_failure_alert("run-scheduled", exc)
            return 1
        if args.json:
            print(json.dumps(_serialize_for_json(_scheduled_result_to_dict(result)), ensure_ascii=False, indent=2))
        else:
            print(format_scheduled_result(result))
        return 0

    if args.command == "send-preview":
        pipeline.initialize()
        try:
            items = pipeline.generate_preview_source(
                source_name=args.source,
                audience=args.audience,
                exercise_profile=args.exercise_profile,
                provider=args.provider,
                limit=args.limit,
                persist=args.persist,
            )
        except Exception as exc:  # pragma: no cover - defensive CLI guard
            print(f"Send preview failed during generation: {exc}", file=sys.stderr)
            pipeline.send_command_failure_alert("send-preview", exc)
            return 1

        export_results = _maybe_export_items(items, output_dir=args.export_dir, formats=args.export_formats)
        payloads = []
        for index, item in enumerate(items):
            if (
                not args.allow_low_score
                and item.preview.score.total_score < pipeline.config.selection.min_total_score
            ):
                payloads.append(
                    {
                        "title": item.package.optimized_title,
                        "response": {
                            "skipped": True,
                            "reason": (
                                f"score {item.preview.score.total_score} below threshold "
                                f"{pipeline.config.selection.min_total_score}"
                            ),
                        },
                        "export": export_results[index] if export_results else None,
                    }
                )
                continue
            title, markdown_text = render_dingtalk_markdown(item)
            if args.send:
                webhook_url = os.getenv(pipeline.config.delivery.webhook_env, "")
                secret = os.getenv(pipeline.config.delivery.secret_env or "", "") if pipeline.config.delivery.secret_env else None
                if not webhook_url:
                    print(
                        f"Send preview failed: missing env {pipeline.config.delivery.webhook_env}",
                        file=sys.stderr,
                    )
                    return 1
                client = DingTalkBotClient(webhook_url=webhook_url, secret=secret)
                response = client.send_markdown(title=title, text=markdown_text)
            else:
                response = {"dry_run": True}
            payloads.append(
                {
                    "title": title,
                    "markdown": markdown_text,
                    "response": response,
                    "export": export_results[index] if export_results else None,
                }
            )

        if args.json:
            print(json.dumps(payloads, ensure_ascii=False, indent=2))
        else:
            for payload in payloads:
                print(format_send_preview(payload))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def preview_to_dict(item: PreviewItem) -> dict[str, object]:
    return _serialize_for_json(
        {
            "candidate": asdict(item.candidate),
            "article": asdict(item.article),
            "score": asdict(item.score),
        }
    )


def format_preview(item: PreviewItem, index: int) -> str:
    reasons = "\n".join(f"  - {reason}" for reason in item.score.reasons)
    return (
        f"[{index}] {item.article.title}\n"
        f"  source: {item.article.source_name}\n"
        f"  url: {item.article.canonical_url}\n"
        f"  words: {item.article.word_count}\n"
        f"  total_score: {item.score.total_score}\n"
        f"  excerpt: {item.article.excerpt[:180]}\n"
        f"  reasons:\n{reasons}\n"
    )


def generated_preview_to_dict(item: GeneratedPreviewItem, export: dict[str, object] | None = None) -> dict[str, object]:
    return _serialize_for_json(
        {
            "preview": preview_to_dict(item.preview),
            "package": asdict(item.package),
            "export": export,
        }
    )


def review_queue_item_to_dict(item: ReviewQueueItem) -> dict[str, object]:
    return _serialize_for_json(asdict(item))


def format_generated_preview(item: GeneratedPreviewItem, index: int, export: dict[str, object] | None = None) -> str:
    package = item.package
    first_question = package.reading_questions[0] if package.reading_questions else None
    lines = [
        f"[{index}] {package.optimized_title}",
        f"  audience: {package.audience}",
        f"  source: {item.preview.article.source_name}",
        f"  score: {item.preview.score.total_score}",
        f"  provider: {package.generator_provider}/{package.generator_model}",
        f"  summary: {package.summary[:220]}",
        f"  teaching_value: {package.teaching_value[:220]}",
        f"  keywords: {', '.join(package.keywords)}",
        f"  reading_words: {len(package.reading_passage.split())}",
        f"  reading_questions: {len(package.reading_questions)}",
        f"  cloze_questions: {len(package.cloze_questions)}",
        f"  task_timings: {package.task_timings}",
    ]
    if export:
        lines.append(f"  export_dir: {export.get('directory')}")
    if first_question:
        lines.append(f"  sample_question: {first_question.stem}")
    return "\n".join(lines) + "\n"


def format_review_queue_item(item: ReviewQueueItem, index: int) -> str:
    lines = [
        f"[{index}] queue_id={item.queue_id} | {item.optimized_title}",
        f"  source: {item.source_name}",
        f"  score: {item.score_total}",
        f"  recommendation: {item.review_recommendation}",
        f"  status: {item.status}",
        f"  audience: {item.audience} | exercise_profile: {item.exercise_profile}",
    ]
    if item.reviewer_note:
        lines.append(f"  note: {item.reviewer_note}")
    if item.export_directory:
        lines.append(f"  export_dir: {item.export_directory}")
    return "\n".join(lines) + "\n"


def _serialize_for_json(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_for_json(item) for item in value]
    return value


def format_doctor_report(report: dict[str, object]) -> str:
    llm = report["llm"]
    providers = report["providers"]
    delivery = report["delivery"]
    lines = [
        f"provider_mode: {llm['provider_mode']}",
        f"primary_provider: {llm['primary_provider']}",
        f"fallback_providers: {', '.join(llm['fallback_providers']) or '(none)'}",
        f"enabled_provider_count: {llm['enabled_provider_count']}",
        f"available_provider_count: {llm['available_provider_count']}",
        "providers:",
    ]
    for provider in providers:
        lines.append(
            "  - "
            f"{provider['name']} | enabled={provider['enabled']} | model={provider['model']} | "
            f"api_key_present={provider['api_key_present']}"
        )
    lines.extend(
        [
            f"delivery_webhook_present: {delivery['webhook_present']}",
            f"delivery_secret_present: {delivery['secret_present']}",
            f"alerting_enabled: {report['alerting']['enabled']}",
            f"alert_webhook_present: {report['alerting']['webhook_present']}",
            f"alert_secret_present: {report['alerting']['secret_present']}",
        ]
    )
    missing = report["missing_items"]
    if missing:
        lines.append("missing_items:")
        for item in missing:
            lines.append(f"  - {item}")
    else:
        lines.append("missing_items: none")
    lines.append(f"ready: {report['ready']}")
    return "\n".join(lines)


def format_smoke_report(report: dict[str, object]) -> str:
    response = report["response"]
    return "\n".join(
        [
            f"provider: {report['provider']}",
            f"model: {report['model']}",
            f"ok: {response.get('ok')}",
            f"mode: {response.get('mode')}",
            f"message: {response.get('message')}",
        ]
    )


def format_beta_report(report: dict[str, object]) -> str:
    lines = [
        f"live_requested: {report['live_requested']}",
        "router_chain:",
    ]
    for row in report["router_chain"]:
        segment = (
            "  - "
            f"{row['role']} | {row['name']} | model={row['model']} | "
            f"api_key_present={row['api_key_present']}"
        )
        if "live_status" in row:
            segment += f" | live_status={row['live_status']}"
        lines.append(segment)
    delivery = report["delivery"]
    lines.extend(
        [
            f"delivery_webhook_present: {delivery['webhook_present']}",
            f"delivery_secret_present: {delivery['secret_present']}",
            f"alerting_enabled: {report['alerting']['enabled']}",
            f"alert_webhook_present: {report['alerting']['webhook_present']}",
            f"alert_secret_present: {report['alerting']['secret_present']}",
            f"ready_generation: {report['ready_generation']}",
            f"ready_delivery: {report['ready_delivery']}",
            f"ready_alerting: {report['ready_alerting']}",
        ]
    )
    missing = report["missing_items"]
    if missing:
        lines.append("missing_items:")
        for item in missing:
            lines.append(f"  - {item}")
    else:
        lines.append("missing_items: none")
    lines.append(f"ready: {report['ready']}")
    return "\n".join(lines)


def format_send_preview(payload: dict[str, object]) -> str:
    if payload.get("response", {}).get("skipped"):
        lines = [
            f"title: {payload['title']}",
            f"response: {payload['response']}",
        ]
        if payload.get("export"):
            lines.append(f"export: {payload['export']}")
        return "\n".join(lines)
    lines = [
        f"title: {payload['title']}",
        f"response: {payload['response']}",
    ]
    if payload.get("export"):
        lines.append(f"export: {payload['export']}")
    lines.extend(
        [
            "markdown:",
            str(payload["markdown"]),
        ]
    )
    return "\n".join(lines)


def format_approval_result(result: dict[str, object]) -> str:
    queue_item = result.get("queue_item")
    if isinstance(queue_item, ReviewQueueItem):
        lines = [format_review_queue_item(queue_item, index=1).rstrip()]
    else:
        lines = ["queue_item: unavailable"]
    if result.get("dispatched") is False:
        lines.append("dispatch: skipped")
        return "\n".join(lines)
    if "delivery_status" in result:
        lines.append(f"delivery_status: {result['delivery_status']}")
    if "response" in result:
        lines.append(f"response: {result['response']}")
    if "export" in result:
        lines.append(f"export: {result['export']}")
    return "\n".join(lines)


def format_dispatch_result(result: dict[str, object]) -> str:
    decision = result.get("decision", {})
    lines = [
        f"allowed: {decision.get('allowed')}",
        f"reason: {decision.get('reason')}",
        f"slot: {decision.get('slot')}",
        f"sent_today: {result.get('sent_today')}",
    ]
    items = result.get("items", [])
    if not items:
        lines.append("items: none")
        return "\n".join(lines)
    lines.append("items:")
    for payload in items:
        queue_item = payload.get("queue_item")
        if isinstance(queue_item, ReviewQueueItem):
            lines.append(
                f"  - queue_id={queue_item.queue_id} | status={payload.get('delivery_status')} | "
                f"title={payload.get('title')}"
            )
        else:
            lines.append(f"  - status={payload.get('delivery_status')} | title={payload.get('title')}")
    return "\n".join(lines)


def format_scheduled_result(result: dict[str, object]) -> str:
    lines = [f"now: {result.get('now')}"]
    queued = result.get("queued", {})
    if queued:
        lines.append("queued:")
        for source_name, items in queued.items():
            lines.append(f"  - {source_name}: {len(items)} item(s)")
    else:
        lines.append("queued: none")
    lines.append("dispatch:")
    dispatch_text = format_dispatch_result(result.get("dispatch", {}))
    lines.extend(f"  {line}" for line in dispatch_text.splitlines())
    return "\n".join(lines)


def _maybe_export_items(
    items: list[GeneratedPreviewItem],
    output_dir: str | None,
    formats: str,
) -> list[dict[str, object]] | None:
    if not output_dir:
        return None
    return _export_items(items, output_dir=output_dir, formats=formats)


def _export_items(
    items: list[GeneratedPreviewItem],
    output_dir: str,
    formats: str,
) -> list[dict[str, object]]:
    export_service = ExportService(output_dir=output_dir)
    parsed_formats = _parse_export_formats(formats)
    return [export_service.export_generated_preview(item, formats=parsed_formats) for item in items]


def _parse_export_formats(value: str) -> tuple[str, ...]:
    allowed = {"markdown", "html", "json", "pdf"}
    parts = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    if not parts:
        return ("markdown", "html", "json")
    invalid = [item for item in parts if item not in allowed]
    if invalid:
        raise ValueError(f"Unsupported export format(s): {', '.join(invalid)}")
    return parts


def _parse_now_argument(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _approval_result_to_dict(result: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    queue_item = result.get("queue_item")
    if isinstance(queue_item, ReviewQueueItem):
        payload["queue_item"] = review_queue_item_to_dict(queue_item)
    if "dispatched" in result:
        payload["dispatched"] = result["dispatched"]
    if "delivery_status" in result:
        payload["delivery_status"] = result["delivery_status"]
    if "response" in result:
        payload["response"] = result["response"]
    if "export" in result:
        payload["export"] = result["export"]
    if "title" in result:
        payload["title"] = result["title"]
    return payload


def _dispatch_result_to_dict(result: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision": result.get("decision", {}),
        "sent_today": result.get("sent_today"),
        "items": [],
    }
    for item in result.get("items", []):
        row = dict(item)
        queue_item = row.get("queue_item")
        if isinstance(queue_item, ReviewQueueItem):
            row["queue_item"] = review_queue_item_to_dict(queue_item)
        payload["items"].append(row)
    return payload


def _scheduled_result_to_dict(result: dict[str, object]) -> dict[str, object]:
    return {
        "now": result.get("now"),
        "queued": {
            source_name: [review_queue_item_to_dict(item) for item in items]
            for source_name, items in result.get("queued", {}).items()
        },
        "dispatch": _dispatch_result_to_dict(result.get("dispatch", {})),
    }
