from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from teacher_content_reminder.config import AppConfig
from teacher_content_reminder.generation.prompts import (
    render_cloze_prompt,
    render_extract_facts_prompt,
    render_reading_passage_prompt,
    render_reading_questions_prompt,
    render_title_summary_prompt,
)
from teacher_content_reminder.generation.validator import (
    build_package,
    ensure_package_quality,
    parse_cloze_payload,
    parse_fact_sheet,
    parse_question_list,
    parse_reading_passage,
    parse_title_summary,
)
from teacher_content_reminder.llm.base import LLMClient
from teacher_content_reminder.llm import build_llm_client
from teacher_content_reminder.llm.router import RouterLLMClient
from teacher_content_reminder.models import GeneratedContentPackage, RawArticle


class GenerationService:
    def __init__(self, config: AppConfig, client: LLMClient | None = None) -> None:
        self.config = config
        self._client = client

    @property
    def client(self) -> LLMClient:
        if self._client is None:
            self._client = build_llm_client(self.config)
        return self._client

    def generate(self, article: RawArticle, audience_key: str, exercise_profile_name: str) -> GeneratedContentPackage:
        audience = self.config.audiences[audience_key]
        exercise_profile = self.config.exercise_profiles[exercise_profile_name]
        task_timings: dict[str, float] = {}
        task_providers: dict[str, str] = {}
        task_models: dict[str, str] = {}

        facts_prompt = render_extract_facts_prompt(
            article=article,
            audience_key=audience_key,
            max_input_chars=self.config.generation.max_input_chars,
        )
        facts, provider_name, model_name, elapsed = self._run_task(
            "extract_facts",
            facts_prompt,
            {
                "article": article,
                "audience": audience_key,
            },
            parse_fact_sheet,
        )
        task_timings["extract_facts"] = elapsed
        task_providers["extract_facts"] = provider_name
        task_models["extract_facts"] = model_name

        (optimized_title, summary, teaching_value, traceability_notes), provider_name, model_name, elapsed = self._run_task(
            "generate_title_summary",
            render_title_summary_prompt(article, facts, audience_key),
            {
                "article": article,
                "audience": audience_key,
                "facts": {
                    "topic": facts.topic,
                    "summary": facts.summary,
                    "key_points": facts.key_points,
                    "teaching_value": facts.teaching_value,
                },
            },
            lambda payload: parse_title_summary(
                payload,
                source_text=f"{article.title}\n{article.excerpt}\n{article.raw_text}",
            ),
        )
        task_timings["generate_title_summary"] = elapsed
        task_providers["generate_title_summary"] = provider_name
        task_models["generate_title_summary"] = model_name

        target_words = round(sum(audience.passage_words) / 2)
        reading_passage, provider_name, model_name, elapsed = self._run_task(
            "generate_reading_passage",
            render_reading_passage_prompt(article, facts, audience_key, audience),
            {
                "article": article,
                "audience": audience_key,
                "facts": {
                    "key_points": facts.key_points,
                },
                "target_words": target_words,
            },
            lambda payload: parse_reading_passage(
                payload,
                source_text=f"{article.title}\n{article.excerpt}\n{article.raw_text}",
            ),
        )
        task_timings["generate_reading_passage"] = elapsed
        task_providers["generate_reading_passage"] = provider_name
        task_models["generate_reading_passage"] = model_name

        # Run reading questions and cloze test in parallel — they are independent
        rq_prompt = render_reading_questions_prompt(facts, audience_key, audience, exercise_profile, reading_passage)
        rq_context = {
            "article": article,
            "audience": audience_key,
            "facts": {
                "summary": facts.summary,
                "key_points": facts.key_points,
                "keywords": facts.keywords,
            },
            "question_count": audience.question_count,
            "passage": reading_passage,
        }
        cloze_prompt = render_cloze_prompt(facts, audience_key, audience, reading_passage)
        cloze_context = {
            "article": article,
            "audience": audience_key,
            "facts": {"keywords": facts.keywords},
            "passage": reading_passage,
            "cloze_blanks": audience.cloze_blanks,
        }

        with ThreadPoolExecutor(max_workers=2) as pool:
            rq_future = pool.submit(
                self._run_task,
                "generate_reading_questions",
                rq_prompt,
                rq_context,
                lambda payload: parse_question_list(payload, minimum=audience.question_count, prefix="reading"),
            )
            cloze_future = pool.submit(
                self._run_task,
                "generate_cloze_test",
                cloze_prompt,
                cloze_context,
                lambda payload: parse_cloze_payload(payload, minimum=min(4, audience.cloze_blanks)),
            )
            reading_questions, rq_provider, rq_model, rq_elapsed = rq_future.result()
            (cloze_passage, cloze_questions), cloze_provider, cloze_model, cloze_elapsed = cloze_future.result()

        task_timings["generate_reading_questions"] = rq_elapsed
        task_providers["generate_reading_questions"] = rq_provider
        task_models["generate_reading_questions"] = rq_model

        task_timings["generate_cloze_test"] = cloze_elapsed
        task_providers["generate_cloze_test"] = cloze_provider
        task_models["generate_cloze_test"] = cloze_model

        package = build_package(
            audience=audience_key,
            exercise_profile=exercise_profile_name,
            optimized_title=optimized_title,
            summary=summary,
            teaching_value=teaching_value,
            reading_passage=reading_passage,
            keywords=facts.keywords,
            discussion_points=facts.discussion_points,
            reading_questions=reading_questions,
            cloze_passage=cloze_passage,
            cloze_questions=cloze_questions,
            traceability_notes=traceability_notes,
            task_timings=task_timings,
            task_providers=task_providers,
            task_models=task_models,
            provider=self._summarize_chain(task_providers.values(), fallback=self.client.provider),
            model=self._summarize_chain(task_models.values(), fallback=self.client.model),
        )
        return ensure_package_quality(
            package,
            min_words=audience.passage_words[0],
            max_words=audience.passage_words[1],
            min_questions=audience.question_count,
            min_cloze_questions=min(4, audience.cloze_blanks),
        )

    def _with_context(self, step_name: str, payload: dict[str, object], parser):
        try:
            return parser(payload)
        except Exception as exc:
            snippet = json.dumps(payload, ensure_ascii=False)[:1200]
            raise ValueError(f"{step_name} parse failed: {exc}. Payload snippet: {snippet}") from exc

    def _run_task(self, task_name: str, prompt: str, context: dict[str, object], parser):
        started = time.perf_counter()
        errors: list[str] = []
        for client in self._task_clients(task_name):
            try:
                payload = client.generate(task_name, prompt, context)
                parsed = self._with_context(task_name, payload, parser)
                return parsed, client.provider, client.model, round(time.perf_counter() - started, 3)
            except Exception as exc:
                errors.append(f"{client.provider}:{exc}")
        raise ValueError(f"{task_name} failed across providers. " + " | ".join(errors))

    def _task_clients(self, task_name: str) -> list[LLMClient]:
        if isinstance(self.client, RouterLLMClient):
            return self.client.ordered_clients(task_name)
        return [self.client]

    def _summarize_chain(self, values, fallback: str) -> str:
        ordered_unique: list[str] = []
        for value in values:
            if value not in ordered_unique:
                ordered_unique.append(value)
        return " -> ".join(ordered_unique) if ordered_unique else fallback
