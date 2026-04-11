from __future__ import annotations

from teacher_content_reminder.config import AudienceConfig, ExerciseProfileConfig
from teacher_content_reminder.models import FactSheet, RawArticle


def render_extract_facts_prompt(article: RawArticle, audience_key: str, max_input_chars: int) -> str:
    truncated = article.raw_text[:max_input_chars]
    return f"""
You are preparing a teacher-facing English content package.

Task: extract core facts from the source article.
Audience: {audience_key}
Source title: {article.title}
Source category: {article.source_category}
Source excerpt: {article.excerpt}
Source text:
{truncated}

Rules:
- Use only facts that are supported by the source text.
- Do not invent names, dates, numbers, locations, or quotations.
- Keep the summary factual and concise.
- key_points: 3 to 5 short bullet-style strings.
- keywords: 4 to 6 short items useful for vocabulary teaching.
- discussion_points: 2 to 4 classroom discussion prompts.
- teaching_value: explain why the article is useful for English teaching.

Return a single JSON object with:
- topic: short topic label
- angle: what makes this article interesting or timely
- summary: 2 to 3 sentences
- key_points: array of strings
- keywords: array of strings
- discussion_points: array of strings
- teaching_value: string
""".strip()


def render_title_summary_prompt(article: RawArticle, facts: FactSheet, audience_key: str) -> str:
    return f"""
You are refining the final teaching package metadata.

Audience: {audience_key}
Original title: {article.title}
Facts summary: {facts.summary}
Key points: {facts.key_points}

Rules:
- Keep the title concise, vivid, and classroom-friendly.
- Keep the summary accurate and traceable to the source facts.
- Do not exaggerate or add unsupported claims.
- Preserve dates, years, names, places, and key numbers exactly when they appear in the source facts.
- traceability_notes should mention where the factual grounding comes from.

Return a single JSON object with:
- optimized_title: string
- summary: 2 to 4 sentences
- teaching_value: 1 to 2 sentences
- traceability_notes: array with 2 to 4 short notes
""".strip()


def render_reading_passage_prompt(article: RawArticle, facts: FactSheet, audience_key: str, audience: AudienceConfig) -> str:
    return f"""
You are rewriting an English reading passage for teachers.

Audience: {audience_key}
CEFR target: {audience.cefr}
Target word range: {audience.passage_words[0]}-{audience.passage_words[1]}
Original title: {article.title}
Facts: {facts.key_points}

Rules:
- Write a coherent classroom-ready reading passage in English.
- Stay within the target word range.
- Preserve the source facts, but rewrite in clear teaching-friendly language.
- Preserve dates, years, names, places, and key numbers exactly when they appear in the source.
- Use an informative tone, not a promotional or conversational tone.
- Do not add facts that are not supported by the source.

Return a single JSON object with:
- reading_passage: string
""".strip()


def render_reading_questions_prompt(
    facts: FactSheet,
    audience_key: str,
    audience: AudienceConfig,
    exercise_profile: ExerciseProfileConfig,
    passage: str,
) -> str:
    return f"""
Generate reading comprehension questions for the following passage.

Audience: {audience_key}
Question count: {audience.question_count}
Include answers: {exercise_profile.include_answers}
Include explanations: {exercise_profile.include_explanations}
Facts summary: {facts.summary}
Passage:
{passage}

Rules:
- Create exactly {audience.question_count} multiple-choice questions.
- Cover a mix of main idea, detail, vocabulary in context, inference, and purpose when possible.
- Every question must have exactly 4 options.
- Use plausible distractors grounded in the topic. Avoid joke answers and avoid meta options such as "the passage says" or "this question asks".
- Vary the correct answer positions across A, B, C, and D.
- Explanations should briefly justify the answer using passage evidence.

Return a single JSON object with:
- questions: array of objects

Each question object must contain:
- question_id
- question_type
- stem
- options: array of 4 strings, each already labeled like "A. ..."
- answer: one of "A", "B", "C", "D"
- explanation
""".strip()


def render_cloze_prompt(
    facts: FactSheet,
    audience_key: str,
    audience: AudienceConfig,
    passage: str,
) -> str:
    return f"""
Generate a cloze exercise for the following passage.

Audience: {audience_key}
Blank count target: {audience.cloze_blanks}
Keywords: {facts.keywords}
Passage:
{passage}

Rules:
- Rewrite the passage as a cloze passage with numbered blanks such as "(1)", "(2)", "(3)".
- Create exactly {audience.cloze_blanks} blanks when possible.
- Choose useful vocabulary words or short phrases from the passage, not random trivia questions.
- For each blank, create exactly 4 short options. Prefer single words or short phrases, not full sentences.
- Vary the correct answer positions across A, B, C, and D.
- The question stem should refer to a blank number, for example "Choose the best answer for blank (1)."
- Avoid meta options such as "the passage directly answers this question."

Return a single JSON object with:
- cloze_passage: string
- questions: array of objects

Each question object must contain:
- question_id
- question_type
- stem
- options: array of 4 strings, each already labeled like "A. ..."
- answer: one of "A", "B", "C", "D"
- explanation
""".strip()
