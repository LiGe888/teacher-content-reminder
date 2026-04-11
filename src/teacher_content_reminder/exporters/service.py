from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess

from teacher_content_reminder.exporters.rendering import (
    EXPORT_VARIANTS,
    build_export_payload,
    render_print_html,
    render_print_markdown,
)
from teacher_content_reminder.models import GeneratedPreviewItem
from teacher_content_reminder.utils import slugify


class ExportService:
    def __init__(self, output_dir: str | Path = ".exports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_generated_preview(
        self,
        item: GeneratedPreviewItem,
        formats: tuple[str, ...] = ("markdown", "html", "json"),
    ) -> dict[str, object]:
        export_dir = self._build_export_dir(item)
        export_dir.mkdir(parents=True, exist_ok=True)

        results: dict[str, object] = {
            "directory": str(export_dir.resolve()),
            "formats": list(formats),
            "variants": list(EXPORT_VARIANTS),
        }
        payload = build_export_payload(item)

        for variant in EXPORT_VARIANTS:
            variant_result: dict[str, object] = {}
            title, markdown_text = render_print_markdown(item, variant=variant)
            _, html_text = render_print_html(item, variant=variant)

            if "markdown" in formats:
                path = export_dir / f"{variant}_worksheet.md"
                path.write_text(markdown_text, encoding="utf-8")
                variant_result["markdown"] = str(path.resolve())
                if variant == "teacher":
                    alias = export_dir / "worksheet.md"
                    alias.write_text(markdown_text, encoding="utf-8")
                    results["markdown"] = str(alias.resolve())

            if "html" in formats:
                path = export_dir / f"{variant}_worksheet.html"
                path.write_text(html_text, encoding="utf-8")
                variant_result["html"] = str(path.resolve())
                if variant == "teacher":
                    alias = export_dir / "worksheet.html"
                    alias.write_text(html_text, encoding="utf-8")
                    results["html"] = str(alias.resolve())

            if "pdf" in formats:
                variant_result["pdf"] = self._export_pdf(export_dir, html_text, title=title, variant=variant)

            results[variant] = variant_result

        if "json" in formats:
            path = export_dir / "package.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
            results["json"] = str(path.resolve())

        return results

    def _build_export_dir(self, item: GeneratedPreviewItem) -> Path:
        date_segment = item.package.generated_at.date().isoformat()
        source_segment = slugify(item.preview.article.source_name, default="source")
        title_segment = slugify(item.package.optimized_title, default="worksheet")
        return self.output_dir / date_segment / source_segment / title_segment

    def _export_pdf(self, export_dir: Path, html_text: str, title: str, variant: str) -> dict[str, object]:
        html_path = export_dir / f"{variant}_worksheet.print.html"
        html_path.write_text(html_text, encoding="utf-8")
        pdf_path = export_dir / f"{variant}_worksheet.pdf"

        wkhtmltopdf = shutil.which("wkhtmltopdf")
        if wkhtmltopdf:
            completed = subprocess.run(
                [wkhtmltopdf, str(html_path), str(pdf_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and pdf_path.exists():
                return {"path": str(pdf_path.resolve()), "status": "ok", "engine": "wkhtmltopdf"}
            return {
                "status": "failed",
                "engine": "wkhtmltopdf",
                "error": (completed.stderr or completed.stdout or "").strip()[:500],
            }

        weasyprint = shutil.which("weasyprint")
        if weasyprint:
            completed = subprocess.run(
                [weasyprint, str(html_path), str(pdf_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and pdf_path.exists():
                return {"path": str(pdf_path.resolve()), "status": "ok", "engine": "weasyprint"}
            return {
                "status": "failed",
                "engine": "weasyprint",
                "error": (completed.stderr or completed.stdout or "").strip()[:500],
            }

        return {
            "status": "unavailable",
            "reason": "No PDF engine found. Use worksheet.html and print to PDF from a browser.",
            "html_path": str(html_path.resolve()),
            "title": title,
        }


def _json_default(value: object) -> str:
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return iso()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")
