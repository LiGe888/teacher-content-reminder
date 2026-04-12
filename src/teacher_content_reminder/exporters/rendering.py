from __future__ import annotations

from dataclasses import asdict
from html import escape

from teacher_content_reminder.models import GeneratedPreviewItem


EXPORT_VARIANTS = ("teacher", "student")


def render_print_markdown(item: GeneratedPreviewItem, variant: str = "teacher") -> tuple[str, str]:
    _require_variant(variant)
    package = item.package
    article = item.preview.article
    title = package.optimized_title
    extension = _build_extension_activities(item)
    preview_prompts = _build_preview_prompts(item)

    lines = [
        f"# {title}",
        "",
        f"- Template: {variant}",
        f"- Audience: {package.audience}",
        f"- Source: {article.source_name}",
        f"- Original Title: {article.title}",
        f"- Score: {item.preview.score.total_score}",
    ]
    if variant == "teacher":
        lines.append(f"- Generator: {package.generator_provider} / {package.generator_model}")

    if article.lead_image_url:
        lines.extend(["", f"![cover]({article.lead_image_url})"])

    if variant == "teacher":
        lines.extend(
            [
                "",
                "## Summary",
                package.summary,
                "",
                "## Teaching Value",
                package.teaching_value,
            ]
        )
    else:
        lines.extend(["", "## Before You Read"])
        for prompt in preview_prompts:
            lines.append(f"- {prompt}")

    lines.extend(
        [
            "",
            "## Keywords",
            ", ".join(package.keywords),
            "",
            "## Reading Passage",
            package.reading_passage,
            "",
            "## Reading Questions",
        ]
    )

    for index, question in enumerate(package.reading_questions, start=1):
        lines.append(f"{index}. {question.stem}")
        for option in question.options:
            lines.append(f"   {option}")

    lines.extend(
        [
            "",
            "## Cloze Passage",
            package.cloze_passage,
            "",
            "## Cloze Questions",
        ]
    )
    for index, question in enumerate(package.cloze_questions, start=1):
        lines.append(f"{index}. {question.stem}")
        for option in question.options:
            lines.append(f"   {option}")

    lines.extend(["", "## Extension Activities"])
    for activity in extension:
        lines.append(f"- {activity}")

    if variant == "teacher":
        lines.extend(["", "## Answer Key", "", "### Reading Questions"])
        for index, question in enumerate(package.reading_questions, start=1):
            lines.append(f"{index}. {question.answer} - {question.explanation}")

        lines.extend(["", "### Cloze Questions"])
        for index, question in enumerate(package.cloze_questions, start=1):
            lines.append(f"{index}. {question.answer} - {question.explanation}")

        lines.extend(["", "## Discussion Points"])
        for point in package.discussion_points:
            lines.append(f"- {point}")

        lines.extend(["", "## Traceability Notes"])
        for note in package.traceability_notes:
            lines.append(f"- {note}")
    else:
        lines.extend(["", "## Reflection"])
        lines.append("- Which part of the passage was easiest to understand? Why?")
        lines.append("- Which question was the hardest? Explain your thinking in English.")

    lines.extend(["", "## Source", article.canonical_url])
    return title, "\n".join(lines)


def render_print_html(item: GeneratedPreviewItem, variant: str = "teacher") -> tuple[str, str]:
    _require_variant(variant)
    package = item.package
    article = item.preview.article
    title = package.optimized_title
    extension = _build_extension_activities(item)
    preview_prompts = _build_preview_prompts(item)

    reading_questions = "".join(
        _question_html(index, question.stem, question.options)
        for index, question in enumerate(package.reading_questions, start=1)
    )
    cloze_questions = "".join(
        _question_html(index, question.stem, question.options)
        for index, question in enumerate(package.cloze_questions, start=1)
    )
    extension_rows = "".join(f"<li>{escape(text)}</li>" for text in extension)
    keywords = "".join(f'<span class="badge">{escape(keyword)}</span>' for keyword in package.keywords)
    cover_html = (
        f'<img class="cover" src="{escape(article.lead_image_url)}" alt="cover" />'
        if article.lead_image_url
        else ""
    )

    teacher_panel = ""
    answer_section = ""
    if variant == "teacher":
        answer_rows = "".join(
            f"<tr><td>Reading {index}</td><td>{escape(question.answer)}</td><td>{escape(question.explanation)}</td></tr>"
            for index, question in enumerate(package.reading_questions, start=1)
        ) + "".join(
            f"<tr><td>Cloze {index}</td><td>{escape(question.answer)}</td><td>{escape(question.explanation)}</td></tr>"
            for index, question in enumerate(package.cloze_questions, start=1)
        )
        discussion_rows = "".join(f"<li>{escape(point)}</li>" for point in package.discussion_points)
        traceability_rows = "".join(f"<li>{escape(note)}</li>" for note in package.traceability_notes)
        teacher_panel = f"""
    <section class="panel">
      <h2>Summary</h2>
      <p>{escape(package.summary)}</p>
      <h2>Teaching Value</h2>
      <p>{escape(package.teaching_value)}</p>
      <h2>Keywords</h2>
      <div>{keywords}</div>
    </section>"""
        answer_section = f"""
    <section class="page-break">
      <h2>Answer Key</h2>
      <table class="answer-table">
        <thead>
          <tr><th>Question</th><th>Answer</th><th>Explanation</th></tr>
        </thead>
        <tbody>
          {answer_rows}
        </tbody>
      </table>
      <h2>Discussion Points</h2>
      <ul>{discussion_rows}</ul>
      <h2>Traceability Notes</h2>
      <ul>{traceability_rows}</ul>
      <h2>Source</h2>
      <p><a href="{escape(article.canonical_url)}">{escape(article.canonical_url)}</a></p>
    </section>"""
    else:
        preview_rows = "".join(f"<li>{escape(text)}</li>" for text in preview_prompts)
        teacher_panel = f"""
    <section class="panel">
      <h2>Before You Read</h2>
      <ul>{preview_rows}</ul>
      <h2>Keywords</h2>
      <div>{keywords}</div>
    </section>"""
        answer_section = f"""
    <section class="page-break">
      <h2>Reflection</h2>
      <ul>
        <li>Which part of the passage was easiest to understand? Why?</li>
        <li>Which question was the hardest? Explain your thinking in English.</li>
      </ul>
      <h2>Source</h2>
      <p><a href="{escape(article.canonical_url)}">{escape(article.canonical_url)}</a></p>
    </section>"""

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} ({escape(variant)})</title>
  <!-- generation metadata -->
  <meta name="generator-provider" content="{escape(package.generator_provider)}" />
  <meta name="generator-model" content="{escape(package.generator_model)}" />
  <meta name="generated-at" content="{escape(package.generated_at.isoformat())}" />
  <meta name="source-url" content="{escape(article.canonical_url)}" />
  <meta name="audience" content="{escape(package.audience)}" />
  <meta name="score" content="{item.preview.score.total_score}" />
  <style>
    :root {{
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #d1d5db;
      --panel: #f8fafc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: white;
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.55;
    }}
    main {{
      width: min(920px, calc(100vw - 48px));
      margin: 32px auto 64px;
    }}
    h1, h2, h3 {{ line-height: 1.2; }}
    h2 {{
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
      margin-top: 28px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.95rem;
      margin-bottom: 20px;
    }}
    .cover {{
      width: 100%;
      max-height: 380px;
      object-fit: cover;
      border-radius: 12px;
      margin: 16px 0 24px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px;
      margin: 18px 0;
    }}
    .question {{
      margin-bottom: 18px;
      page-break-inside: avoid;
    }}
    .question ul {{
      margin: 8px 0 0 20px;
      padding: 0;
    }}
    .question li {{
      margin: 6px 0;
    }}
    .answer-table {{
      width: 100%;
      border-collapse: collapse;
    }}
    .answer-table th, .answer-table td {{
      border: 1px solid var(--line);
      padding: 10px;
      vertical-align: top;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      margin-right: 8px;
      margin-bottom: 8px;
      font-size: 0.92rem;
    }}
    .page-break {{
      page-break-before: always;
    }}
    @media print {{
      body {{ margin: 0; }}
      main {{ width: auto; margin: 0; padding: 14mm; }}
      a {{ color: inherit; text-decoration: none; }}
      .panel {{ break-inside: avoid; }}
      .doc-meta {{ display: block; }}
    }}
    .doc-meta {{
      display: block;
      font-size: 0.78rem;
      color: var(--muted);
      border-top: 1px solid var(--line);
      padding: 10px 0 4px;
      margin-top: 32px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{escape(title)}</h1>
    <div class="meta">
      Template: {escape(variant)} |
      Audience: {escape(package.audience)} |
      Source: {escape(article.source_name)} |
      Score: {item.preview.score.total_score}
    </div>
    {cover_html}
    {teacher_panel}
    <section>
      <h2>Reading Passage</h2>
      <p>{escape(package.reading_passage)}</p>
    </section>
    <section>
      <h2>Reading Questions</h2>
      {reading_questions}
    </section>
    <section>
      <h2>Cloze Passage</h2>
      <p>{escape(package.cloze_passage)}</p>
      <h2>Cloze Questions</h2>
      {cloze_questions}
    </section>
    <section class="panel">
      <h2>Extension Activities</h2>
      <ul>{extension_rows}</ul>
    </section>
    {answer_section}
  </main>
  <footer class="doc-meta">
    Generated: {escape(package.generated_at.strftime("%Y-%m-%d %H:%M UTC"))} |
    Provider: {escape(package.generator_provider)} / {escape(package.generator_model)} |
    Score: {item.preview.score.total_score} |
    Source: <a href="{escape(article.canonical_url)}">{escape(article.source_name)}</a>
  </footer>
</body>
</html>"""
    return title, html


def build_export_payload(item: GeneratedPreviewItem) -> dict[str, object]:
    return {
        "preview": asdict(item.preview),
        "package": asdict(item.package),
        "extension_activities": _build_extension_activities(item),
        "student_prompts": _build_preview_prompts(item),
        "variants": list(EXPORT_VARIANTS),
    }


def _question_html(index: int, stem: str, options: list[str]) -> str:
    options_html = "".join(f"<li>{escape(option)}</li>" for option in options)
    return (
        '<div class="question">'
        f"<strong>{index}. {escape(stem)}</strong>"
        f"<ul>{options_html}</ul>"
        "</div>"
    )


def _build_extension_activities(item: GeneratedPreviewItem) -> list[str]:
    package = item.package
    article = item.preview.article
    keyword = package.keywords[0] if package.keywords else "science"
    discussion = package.discussion_points[0] if package.discussion_points else f"How does {keyword} change everyday life?"
    return [
        f"Warm-up: Ask students to predict what they might learn from the title '{package.optimized_title}'.",
        f"Speaking task: In pairs, discuss this question: {discussion}",
        f"Writing task: Write 120-150 words explaining why {keyword} matters in real life.",
        f"Research task: Find one recent example related to {keyword} and compare it with this article.",
        f"Extension topic: Connect this reading to a broader theme such as teamwork, innovation, ethics, or global cooperation mentioned in {article.source_name}.",
    ]


def _build_preview_prompts(item: GeneratedPreviewItem) -> list[str]:
    keyword_one = item.package.keywords[0] if item.package.keywords else "science"
    keyword_two = item.package.keywords[1] if len(item.package.keywords) > 1 else keyword_one
    return [
        f"Look at the title and predict what the article may say about {keyword_one}.",
        f"Explain how {keyword_two} might connect to the topic before you start reading.",
        "Read the first paragraph quickly and guess the writer’s main purpose.",
    ]


def _require_variant(variant: str) -> None:
    if variant not in EXPORT_VARIANTS:
        raise ValueError(f"Unsupported export variant: {variant}")
