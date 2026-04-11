from __future__ import annotations

from collections import Counter
from typing import Any
import re

from teacher_content_reminder.llm.base import LLMClient
from teacher_content_reminder.utils import clean_text


STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "been",
    "because",
    "before",
    "being",
    "between",
    "could",
    "earth",
    "first",
    "from",
    "have",
    "into",
    "more",
    "mission",
    "people",
    "said",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "under",
    "using",
    "were",
    "which",
    "while",
    "with",
    "would",
}


class MockLLMClient(LLMClient):
    provider = "mock"

    def __init__(self, model: str = "mock-teacher-v1") -> None:
        self.model = model

    def generate(self, task_name: str, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        if task_name == "smoke_test":
            return {
                "ok": True,
                "provider": self.provider,
                "mode": "smoke_test",
                "message": "Mock JSON output is working.",
            }

        article = context["article"]
        audience = context.get("audience", "senior")
        facts = context.get("facts", {})
        passage = context.get("passage", "")

        if task_name == "extract_facts":
            sentences = _sentences(article.raw_text or article.excerpt)
            key_points = sentences[:3] or [clean_text(article.excerpt or article.title)]
            keywords = _top_keywords(article.title, article.raw_text, max_items=6)
            topic = _topic_from_category(article.source_category)
            angle = key_points[0]
            summary = " ".join(sentences[:2]) or clean_text(article.excerpt)
            discussion_points = [
                f"What makes this {topic.lower()} story relevant to students today?",
                "Which detail from the text would be most useful in a classroom discussion?",
                "How could learners connect this event to their own experience or studies?",
            ]
            teaching_value = _teaching_value(topic, article.word_count)
            return {
                "topic": topic,
                "angle": angle,
                "summary": summary[:320],
                "key_points": key_points,
                "keywords": keywords,
                "discussion_points": discussion_points,
                "teaching_value": teaching_value,
            }

        if task_name == "generate_title_summary":
            topic = facts.get("topic", _topic_from_category(article.source_category))
            polished = _polish_title(article.title)
            summary = facts.get("summary") or clean_text(article.excerpt)
            teaching_value = facts.get("teaching_value") or _teaching_value(topic, article.word_count)
            return {
                "optimized_title": polished,
                "summary": summary,
                "teaching_value": teaching_value,
                "traceability_notes": [
                    f"Source article: {article.title}",
                    f"Original link: {article.canonical_url}",
                    "Draft generated in mock mode for local workflow validation.",
                ],
            }

        if task_name == "generate_reading_passage":
            key_points = facts.get("key_points") or _sentences(article.raw_text)[:3]
            target_words = context.get("target_words", 320)
            passage_text = _build_passage(article.title, key_points, audience=audience, target_words=target_words)
            return {"reading_passage": passage_text}

        if task_name == "generate_reading_questions":
            summary = facts.get("summary") or clean_text(article.excerpt)
            key_points = facts.get("key_points") or _sentences(article.raw_text)[:3]
            keywords = facts.get("keywords") or _top_keywords(article.title, article.raw_text, max_items=4)
            count = int(context.get("question_count", 5))
            questions = _build_reading_questions(
                title=_polish_title(article.title),
                summary=summary,
                key_points=key_points,
                keywords=keywords,
                count=count,
            )
            return {"questions": questions}

        if task_name == "generate_cloze_test":
            blanks = int(context.get("cloze_blanks", 8))
            keywords = facts.get("keywords") or _top_keywords(article.title, article.raw_text, max_items=blanks)
            return _build_cloze_payload(passage, keywords=keywords, blanks=blanks)

        raise ValueError(f"Unsupported mock task: {task_name}")


def _sentences(text: str) -> list[str]:
    normalized = clean_text(text).replace("?", ".").replace("!", ".")
    parts = [clean_text(part) for part in re.split(r"[.]\s+", normalized) if clean_text(part)]
    return [part if part.endswith(".") else f"{part}." for part in parts]


def _topic_from_category(category: str) -> str:
    mapping = {
        "science_nature": "Science and Discovery",
        "culture_history": "Culture and History",
        "current_events": "Current Events",
    }
    return mapping.get(category, "General Interest")


def _top_keywords(title: str, text: str, max_items: int = 6) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", f"{title} {text}".lower())
    counts = Counter(token for token in tokens if token not in STOPWORDS)
    ranked = [word for word, _ in counts.most_common(max_items * 2)]
    unique: list[str] = []
    for word in ranked:
        if word not in unique:
            unique.append(word)
        if len(unique) >= max_items:
            break
    return unique or ["science", "students", "discussion"]


def _teaching_value(topic: str, word_count: int) -> str:
    complexity = "moderate" if word_count < 700 else "rich"
    return (
        f"This {topic.lower()} article offers {complexity} factual detail, clear cause-and-effect links, "
        "and enough concrete information for reading questions, vocabulary work, and speaking follow-up."
    )


def _polish_title(title: str) -> str:
    cleaned = clean_text(title.split(" - ")[0])
    if not cleaned:
        return "New Teaching Reading"
    words = cleaned.split()
    if len(words) <= 12:
        return cleaned
    return " ".join(words[:12]).rstrip(",;:.")


def _build_passage(title: str, key_points: list[str], audience: str, target_words: int) -> str:
    intro = (
        f"{_polish_title(title)} is the focus of this reading. "
        f"The article gives learners a clear look at why the event matters."
    )
    transitions = [
        "First, the report explains the basic situation in clear detail.",
        "Next, it adds important facts that help readers understand the bigger picture.",
        "It also shows why the story could lead to further discussion in class.",
        "Finally, readers can think about what this development may mean in the future.",
    ]
    sentences = [intro] + [clean_text(point) for point in key_points] + transitions
    passage = " ".join(sentence for sentence in sentences if sentence)
    words = passage.split()
    if len(words) < target_words:
        filler = (
            " Teachers can use the details to guide prediction, inference, vocabulary practice, "
            "and short speaking tasks after reading."
        )
        while len(words) < target_words:
            passage += filler
            words = passage.split()
    lower, upper = _audience_window(audience, target_words)
    clipped = " ".join(words[:upper])
    if len(clipped.split()) < lower:
        clipped += " Students should pay attention to the timeline, the main evidence, and the final result."
    return clipped


def _audience_window(audience: str, target_words: int) -> tuple[int, int]:
    if audience == "junior":
        return (120, max(220, target_words))
    if audience == "adult":
        return (320, max(650, target_words))
    return (220, max(420, target_words))


def _build_reading_questions(
    title: str,
    summary: str,
    key_points: list[str],
    keywords: list[str],
    count: int,
) -> list[dict[str, Any]]:
    key_point = key_points[0] if key_points else summary
    secondary = key_points[1] if len(key_points) > 1 else summary
    keyword = keywords[0] if keywords else "detail"
    bank = [
        {
            "question_id": "rq1",
            "question_type": "multiple_choice",
            "stem": f"What is the main idea of the passage '{title}'?",
            **_build_labeled_choices(
                clean_text(summary),
                [
                    "It focuses on a private family story with no wider impact.",
                    "It mainly advertises a product connected to the event.",
                    "It argues that the event has already been forgotten.",
                ],
                correct_label="B",
            ),
            "explanation": "The first option best matches the summary and overall focus of the article.",
        },
        {
            "question_id": "rq2",
            "question_type": "multiple_choice",
            "stem": "Which detail is clearly mentioned in the passage?",
            **_build_labeled_choices(
                clean_text(key_point),
                [
                    "The event was canceled before any public update appeared.",
                    "No experts were involved in explaining the event.",
                    "The report says students should ignore the story.",
                ],
                correct_label="C",
            ),
            "explanation": "Option A restates a key supporting detail from the reading.",
        },
        {
            "question_id": "rq3",
            "question_type": "multiple_choice",
            "stem": f"In the passage, the word '{keyword}' is closest in meaning to:",
            **_build_labeled_choices(
                "an important topic or element",
                [
                    "a random mistake",
                    "a private secret",
                    "a school holiday",
                ],
                correct_label="D",
            ),
            "explanation": "The keyword is used as part of the central subject, so the first choice fits best.",
        },
        {
            "question_id": "rq4",
            "question_type": "multiple_choice",
            "stem": "What can readers infer from the article?",
            **_build_labeled_choices(
                "The topic may lead to further discussion or learning activities.",
                [
                    "The event has no connection to real life.",
                    "The report contains only personal opinions and no facts.",
                    "Readers are told not to ask questions about the topic.",
                ],
                correct_label="A",
            ),
            "explanation": "The passage presents concrete information and classroom value, so further discussion is reasonable.",
        },
        {
            "question_id": "rq5",
            "question_type": "multiple_choice",
            "stem": "Why might this passage be useful in an English class?",
            **_build_labeled_choices(
                "It includes clear facts, teachable vocabulary, and discussion value.",
                [
                    "It is too short to support any class activity.",
                    "It avoids all real-world information.",
                    "It only repeats one sentence again and again.",
                ],
                correct_label="B",
            ),
            "explanation": "The article offers enough detail and structure for language-learning tasks.",
        },
        {
            "question_id": "rq6",
            "question_type": "multiple_choice",
            "stem": "Which statement best matches another supporting detail in the text?",
            **_build_labeled_choices(
                clean_text(secondary),
                [
                    "The article says there is no need to follow future updates.",
                    "The text shows that nobody cares about the outcome.",
                    "The report is only about entertainment news.",
                ],
                correct_label="C",
            ),
            "explanation": "Option A reflects another detail provided in the reading passage.",
        },
    ]
    return bank[:count]


def _build_cloze_payload(passage: str, keywords: list[str], blanks: int) -> dict[str, Any]:
    words = passage.split()
    selected: list[str] = []
    for keyword in keywords:
        lowered = keyword.lower()
        if lowered not in selected and any(lowered in token.lower().strip(".,;:!?") for token in words):
            selected.append(lowered)
        if len(selected) >= blanks:
            break

    if len(selected) < blanks:
        for token in words:
            core = token.lower().strip(".,;:!?")
            if len(core) < 5 or core in STOPWORDS or core in selected:
                continue
            selected.append(core)
            if len(selected) >= blanks:
                break

    blank_map: dict[str, str] = {}
    cloze_words = list(words)
    for index, keyword in enumerate(selected, start=1):
        for word_index, token in enumerate(cloze_words):
            core = token.strip(".,;:!?").lower()
            if core == keyword:
                blank_map[str(index)] = token.strip(".,;:!?")
                cloze_words[word_index] = token.replace(token.strip(".,;:!?"), f"({index})")
                break

    questions: list[dict[str, Any]] = []
    for blank_id, answer in blank_map.items():
        distractors = _cloze_distractors(answer)
        label = _rotating_label(int(blank_id))
        choice_payload = _build_labeled_choices(answer, distractors, correct_label=label)
        questions.append(
            {
                "question_id": f"cq{blank_id}",
                "question_type": "cloze_choice",
                "stem": f"Choose the best word for blank ({blank_id}).",
                **choice_payload,
                "explanation": f"The original passage uses '{answer}' in this position.",
            }
        )

    return {
        "cloze_passage": " ".join(cloze_words),
        "questions": questions,
    }


def _cloze_distractors(answer: str) -> list[str]:
    lower = answer.lower()
    return [
        f"{lower}ing" if not lower.endswith("ing") else f"{lower}ed",
        "idea",
        "future",
    ]


def _build_labeled_choices(correct: str, distractors: list[str], correct_label: str) -> dict[str, Any]:
    labels = ["A", "B", "C", "D"]
    insert_at = labels.index(correct_label)
    ordered = [clean_text(item) for item in distractors[:3]]
    ordered.insert(insert_at, clean_text(correct))
    options = [f"{label}. {text}" for label, text in zip(labels, ordered)]
    return {
        "options": options,
        "answer": correct_label,
    }


def _rotating_label(index: int) -> str:
    labels = ["A", "B", "C", "D"]
    return labels[(index - 1) % len(labels)]
