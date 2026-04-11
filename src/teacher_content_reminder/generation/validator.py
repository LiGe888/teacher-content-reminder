from __future__ import annotations

from collections import Counter
from typing import Any
import re

from teacher_content_reminder.models import ExerciseQuestion, FactSheet, GeneratedContentPackage
from teacher_content_reminder.utils import clean_text, utc_now

_GENERIC_OPTION_PATTERNS = (
    r"\bthe passage\b",
    r"\bthe report\b",
    r"\bthis question\b",
    r"\bdirectly answers\b",
    r"\bno wider importance\b",
    r"\bfictional story\b",
    r"\bno evidence or detail\b",
)


def parse_fact_sheet(payload: dict[str, Any]) -> FactSheet:
    _require_keys(payload, ("topic", "angle", "summary", "key_points", "keywords", "discussion_points", "teaching_value"))
    return FactSheet(
        topic=clean_text(str(payload["topic"])),
        angle=clean_text(str(payload["angle"])),
        summary=clean_text(str(payload["summary"])),
        key_points=_coerce_fact_list(payload["key_points"], minimum=2, fallback_prefix="Additional key point"),
        keywords=_coerce_fact_list(payload["keywords"], minimum=3, fallback_prefix="keyword"),
        discussion_points=_coerce_fact_list(
            payload["discussion_points"],
            minimum=2,
            fallback_prefix="Additional discussion point",
        ),
        teaching_value=clean_text(str(payload["teaching_value"])),
    )


def parse_title_summary(payload: dict[str, Any], source_text: str | None = None) -> tuple[str, str, str, list[str]]:
    _require_keys(payload, ("optimized_title", "summary", "teaching_value", "traceability_notes"))
    optimized_title = clean_text(str(payload["optimized_title"]))
    summary = clean_text(str(payload["summary"]))
    teaching_value = clean_text(str(payload["teaching_value"]))
    if source_text:
        _ensure_supported_years(
            [optimized_title, summary, teaching_value],
            source_text=source_text,
            label="title_summary",
        )
    return (
        optimized_title,
        summary,
        teaching_value,
        _coerce_fact_list(payload["traceability_notes"], minimum=2, fallback_prefix="Traceability note"),
    )


def parse_reading_passage(payload: dict[str, Any], source_text: str | None = None) -> str:
    _require_keys(payload, ("reading_passage",))
    passage = clean_text(str(payload["reading_passage"]))
    if len(passage.split()) < 80:
        raise ValueError("Generated reading passage is too short.")
    if source_text:
        _ensure_supported_years([passage], source_text=source_text, label="reading_passage")
    return passage


def parse_question_list(payload: dict[str, Any], minimum: int, prefix: str) -> list[ExerciseQuestion]:
    _require_keys(payload, ("questions",))
    raw_questions = payload["questions"]
    if not isinstance(raw_questions, list) or len(raw_questions) < minimum:
        raise ValueError(f"Expected at least {minimum} questions for {prefix}.")
    questions: list[ExerciseQuestion] = []
    for index, item in enumerate(raw_questions, start=1):
        if isinstance(item, str):
            item = {"stem": item}
        if not isinstance(item, dict):
            raise ValueError(f"Question {index} is not an object.")
        stem = clean_text(str(item.get("stem") or item.get("question") or item.get("prompt") or ""))
        if not stem:
            raise ValueError(f"Question {index} is missing a stem.")
        options = _coerce_question_options(item, minimum=4)
        answer = _coerce_answer_label(item, options)
        if answer not in {"A", "B", "C", "D"}:
            raise ValueError(f"Question {index} has unsupported answer label: {answer}")
        questions.append(
            ExerciseQuestion(
                question_id=clean_text(str(item.get("question_id") or f"{prefix}_{index}")),
                question_type=clean_text(str(item.get("question_type") or prefix)),
                stem=stem,
                options=options,
                answer=answer,
                explanation=clean_text(str(item.get("explanation") or item.get("analysis") or item.get("reason") or "")),
            )
        )
    _validate_question_batch(questions, prefix)
    return questions


def parse_cloze_payload(payload: dict[str, Any], minimum: int) -> tuple[str, list[ExerciseQuestion]]:
    _require_keys(payload, ("cloze_passage",))
    passage = clean_text(str(payload["cloze_passage"]))
    if _count_cloze_blanks(passage) < minimum:
        raise ValueError(f"Expected at least {minimum} blanks in cloze passage.")
    raw_questions = payload.get("questions")
    if raw_questions:
        questions = parse_question_list({"questions": raw_questions}, minimum=minimum, prefix="cloze")
    else:
        questions = _infer_cloze_questions_from_passage(passage, minimum=minimum)
    return passage, questions


def ensure_package_quality(
    package: GeneratedContentPackage,
    min_words: int,
    max_words: int,
    min_questions: int,
    min_cloze_questions: int,
) -> GeneratedContentPackage:
    word_count = len(package.reading_passage.split())
    if word_count < max(80, min_words - 15):
        raise ValueError(f"Reading passage word count {word_count} is below minimum tolerance for target {min_words}.")
    if word_count > max_words + 120:
        raise ValueError(f"Reading passage word count {word_count} is too long for target audience.")
    if len(package.reading_questions) < min_questions:
        raise ValueError("Not enough reading questions were generated.")
    if len(package.cloze_questions) < min_cloze_questions:
        raise ValueError("Not enough cloze questions were generated.")
    return package


def build_package(
    audience: str,
    exercise_profile: str,
    optimized_title: str,
    summary: str,
    teaching_value: str,
    reading_passage: str,
    keywords: list[str],
    discussion_points: list[str],
    reading_questions: list[ExerciseQuestion],
    cloze_passage: str,
    cloze_questions: list[ExerciseQuestion],
    traceability_notes: list[str],
    task_timings: dict[str, float],
    task_providers: dict[str, str],
    task_models: dict[str, str],
    provider: str,
    model: str,
) -> GeneratedContentPackage:
    return GeneratedContentPackage(
        audience=audience,
        exercise_profile=exercise_profile,
        optimized_title=optimized_title,
        summary=summary,
        teaching_value=teaching_value,
        reading_passage=reading_passage,
        keywords=keywords,
        discussion_points=discussion_points,
        reading_questions=reading_questions,
        cloze_passage=cloze_passage,
        cloze_questions=cloze_questions,
        traceability_notes=traceability_notes,
        task_timings=task_timings,
        task_providers=task_providers,
        task_models=task_models,
        generator_provider=provider,
        generator_model=model,
        generated_at=utc_now(),
    )


def _require_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        if key not in payload:
            raise ValueError(f"Missing required key: {key}")


def _string_list(value: Any, minimum: int) -> list[str]:
    if isinstance(value, str):
        candidate_items = _split_listish_string(value)
    elif isinstance(value, list):
        candidate_items = value
    else:
        raise ValueError("Expected a list of strings.")
    normalized = [clean_text(str(item)) for item in candidate_items if clean_text(str(item))]
    if len(normalized) < minimum:
        raise ValueError(f"Expected at least {minimum} non-empty items.")
    return normalized


def _coerce_fact_list(value: Any, minimum: int, fallback_prefix: str) -> list[str]:
    try:
        normalized = _string_list(value, minimum=minimum)
        return normalized
    except ValueError:
        normalized = _string_list(value, minimum=1)
        if len(normalized) == 1:
            expanded = _expand_single_fact_item(normalized[0])
            for item in expanded:
                if item not in normalized:
                    normalized.append(item)
        while len(normalized) < minimum:
            normalized.append(f"{fallback_prefix} {len(normalized) + 1}")
        return normalized[: max(minimum, len(normalized))]


def _split_listish_string(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    lines = [clean_text(line.lstrip("-*0123456789. )(")) for line in cleaned.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) > 1:
        return lines
    if ";" in cleaned:
        return [clean_text(part) for part in cleaned.split(";") if clean_text(part)]
    if "；" in cleaned:
        return [clean_text(part) for part in cleaned.split("；") if clean_text(part)]
    return [cleaned]


def _expand_single_fact_item(value: str) -> list[str]:
    separators = [". ", "; ", "；", ", ", "，", " / "]
    for separator in separators:
        if separator in value:
            items = [clean_text(part) for part in value.split(separator) if clean_text(part)]
            if len(items) > 1:
                return items
    return []


def _coerce_question_options(item: dict[str, Any], minimum: int) -> list[str]:
    raw_options = item.get("options") or item.get("choices")
    if raw_options is None:
        option_keys = ["option_a", "option_b", "option_c", "option_d"]
        raw_options = [item[key] for key in option_keys if key in item]
    if raw_options is None:
        answer_text = clean_text(
            str(
                item.get("answer")
                or item.get("correct_answer")
                or item.get("correctOption")
                or item.get("correct")
                or ""
            )
        )
        if answer_text:
            raw_options = _fallback_options_from_answer(answer_text)
        else:
            raw_options = _fallback_options_from_stem(
                clean_text(str(item.get("question") or item.get("stem") or item.get("prompt") or ""))
            )

    if isinstance(raw_options, dict):
        raw_options = [f"{key}. {value}" for key, value in raw_options.items()]
    elif isinstance(raw_options, str):
        raw_options = _split_optionish_string(raw_options)

    if not isinstance(raw_options, list):
        raw_options = [raw_options]

    normalized: list[str] = []
    for index, option in enumerate(raw_options):
        label = chr(ord("A") + index)
        if isinstance(option, dict):
            text = clean_text(str(option.get("text") or option.get("content") or option.get("value") or ""))
            option_label = clean_text(str(option.get("label") or label)).upper()[:1] or label
            if text:
                normalized.append(f"{option_label}. {text}")
        else:
            text = clean_text(str(option))
            if not text:
                continue
            if len(text) > 2 and text[1] == ".":
                normalized.append(text)
            else:
                normalized.append(f"{label}. {text}")

    if len(normalized) < minimum:
        answer_text = clean_text(
            str(
                item.get("answer")
                or item.get("correct_answer")
                or item.get("correctOption")
                or item.get("correct")
                or ""
            )
        )
        fallbacks = (
            _fallback_options_from_answer(answer_text)
            if answer_text
            else _fallback_options_from_stem(clean_text(str(item.get("question") or item.get("stem") or item.get("prompt") or "")))
        )
        for fallback in fallbacks:
            label = chr(ord("A") + len(normalized))
            if len(normalized) >= minimum:
                break
            text = clean_text(fallback)
            if not text:
                continue
            if len(text) > 2 and text[1] == ".":
                normalized.append(text)
            else:
                normalized.append(f"{label}. {text}")
    if len(normalized) < minimum:
        raise ValueError(f"Expected at least {minimum} non-empty items.")
    return normalized


def _coerce_answer_label(item: dict[str, Any], options: list[str]) -> str:
    raw_answer = clean_text(
        str(
            item.get("answer")
            or item.get("correct_answer")
            or item.get("correctOption")
            or item.get("correct")
            or ""
        )
    )
    if not raw_answer:
        return "A"
    upper = raw_answer.upper()
    if upper in {"A", "B", "C", "D"}:
        return upper
    for option in options:
        if option.upper().startswith(f"{upper}."):
            return upper
    for option in options:
        label = option[0].upper()
        body = clean_text(option[2:] if len(option) > 2 else option)
        if raw_answer == body:
            return label
    return upper[:1]


def _fallback_options_from_answer(answer_text: str) -> list[str]:
    distractors = [
        "It was mainly designed as a routine media event.",
        "The passage says the mission had no scientific or technical purpose.",
        "It focused only on commercial travel plans for tourists.",
    ]
    return [answer_text, *distractors]


def _fallback_options_from_stem(stem: str) -> list[str]:
    prompt_hint = stem or "the passage"
    return [
        f"The passage directly answers this question about {prompt_hint}.",
        "The passage says the event had no wider importance.",
        "The topic is described as a fictional story rather than a real event.",
        "The report claims that no evidence or detail is provided.",
    ]


def _infer_cloze_questions_from_passage(passage: str, minimum: int) -> list[ExerciseQuestion]:
    answers = re.findall(r"\[([^\[\]]+)\]", passage)
    questions: list[ExerciseQuestion] = []
    for index, answer in enumerate(answers, start=1):
        options = _fallback_options_from_answer(clean_text(answer))
        questions.append(
            ExerciseQuestion(
                question_id=f"cloze_{index}",
                question_type="cloze_choice",
                stem=f"Choose the best answer for blank ({index}).",
                options=[f"{chr(ord('A') + idx)}. {option}" for idx, option in enumerate(options[:4])],
                answer="A",
                explanation=f"The original passage uses '{clean_text(answer)}' in this blank.",
            )
        )
    if len(questions) < minimum:
        raise ValueError(f"Unable to infer at least {minimum} cloze questions from passage.")
    return questions


def _split_optionish_string(value: str) -> list[str]:
    cleaned = clean_text(value)
    if not cleaned:
        return []
    option_markers = ["A.", "B.", "C.", "D.", "A)", "B)", "C)", "D)"]
    if sum(marker in cleaned for marker in option_markers) >= 2:
        import re

        parts = re.split(r"(?=[A-D][\.\)])", cleaned)
        items = [clean_text(part) for part in parts if clean_text(part)]
        if len(items) > 1:
            return items
    return _split_listish_string(value)


def _validate_question_batch(questions: list[ExerciseQuestion], prefix: str) -> None:
    if not questions:
        raise ValueError("Question list is empty.")

    normalized_stems = [clean_text(question.stem).lower() for question in questions]
    if len(set(normalized_stems)) < len(normalized_stems):
        raise ValueError("Question stems contain duplicates.")

    answer_counts = Counter(question.answer for question in questions)
    if len(questions) >= 4 and len(answer_counts) == 1:
        raise ValueError("Answer labels are not varied enough.")

    for index, question in enumerate(questions, start=1):
        if len(question.options) != 4:
            raise ValueError(f"Question {index} must have exactly 4 options.")
        meta_hits = sum(1 for option in question.options if _is_generic_option(option))
        if meta_hits >= 2:
            raise ValueError(f"Question {index} contains low-quality meta distractors.")
        if prefix == "cloze":
            if not _looks_like_cloze_stem(question.stem):
                question.stem = f"Choose the best answer for blank ({index})."
            if any(_option_body_word_count(option) > 8 or len(_option_body(option)) > 60 for option in question.options):
                raise ValueError(f"Cloze question {index} has options that are too long.")


def _is_generic_option(option: str) -> bool:
    body = _option_body(option).lower()
    return any(re.search(pattern, body) for pattern in _GENERIC_OPTION_PATTERNS)


def _option_body(option: str) -> str:
    text = clean_text(option)
    if len(text) > 2 and text[1] == ".":
        return clean_text(text[2:])
    return text


def _option_body_word_count(option: str) -> int:
    return len(_option_body(option).split())


def _looks_like_cloze_stem(stem: str) -> bool:
    normalized = clean_text(stem).lower()
    return "blank" in normalized or "gap" in normalized


def _count_cloze_blanks(passage: str) -> int:
    patterns = [
        r"\(\d+\)",
        r"_{3,}",
        r"\[[^\[\]]+\]",
    ]
    return sum(len(re.findall(pattern, passage)) for pattern in patterns)


def _ensure_supported_years(texts: list[str], source_text: str, label: str) -> None:
    """Reject generated years that are not grounded in the source text."""
    source_years = set(re.findall(r"\b(?:19|20)\d{2}\b", source_text))
    if not source_years:
        return
    generated_years: set[str] = set()
    for text in texts:
        generated_years.update(re.findall(r"\b(?:19|20)\d{2}\b", text))
    unsupported = sorted(generated_years - source_years)
    if unsupported:
        raise ValueError(
            f"{label} references unsupported year(s): {', '.join(unsupported)}"
        )
