from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import sqlite3
from zoneinfo import ZoneInfo

from teacher_content_reminder.models import (
    ActivityLogEntry,
    ArticleCandidate,
    ArticleScore,
    DeliveryEvent,
    ExerciseQuestion,
    GeneratedContentPackage,
    GeneratedPreviewItem,
    PreviewItem,
    RawArticle,
    ReviewQueueItem,
)
from teacher_content_reminder.utils import hash_text, parse_datetime, utc_now


class SQLiteRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(".data") / "teacher-content-reminder.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS raw_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    source_category TEXT NOT NULL,
                    source_url TEXT NOT NULL UNIQUE,
                    canonical_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    published_at TEXT,
                    excerpt TEXT,
                    lead_image_url TEXT,
                    raw_html TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    fetched_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    score_total REAL,
                    score_payload TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS content_packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_url TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    exercise_profile TEXT NOT NULL,
                    optimized_title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    teaching_value TEXT NOT NULL,
                    reading_passage TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    discussion_points_json TEXT NOT NULL,
                    traceability_notes_json TEXT NOT NULL,
                    cover_image_url TEXT,
                    generator_provider TEXT NOT NULL,
                    generator_model TEXT NOT NULL,
                    generation_payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS exercise_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_package_id INTEGER NOT NULL,
                    exercise_type TEXT NOT NULL,
                    question_payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(content_package_id) REFERENCES content_packages(id)
                );

                CREATE TABLE IF NOT EXISTS review_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_package_id INTEGER NOT NULL UNIQUE,
                    article_url TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    exercise_profile TEXT NOT NULL,
                    optimized_title TEXT NOT NULL,
                    score_total REAL NOT NULL,
                    review_recommendation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reviewer_note TEXT DEFAULT '',
                    export_directory TEXT DEFAULT '',
                    dingtalk_response TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    approved_at TEXT,
                    sent_at TEXT,
                    FOREIGN KEY(content_package_id) REFERENCES content_packages(id)
                );

                CREATE TABLE IF NOT EXISTS delivery_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_queue_id INTEGER,
                    content_package_id INTEGER,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(review_queue_id) REFERENCES review_queue(id),
                    FOREIGN KEY(content_package_id) REFERENCES content_packages(id)
                );

                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source_name TEXT DEFAULT '',
                    review_queue_id INTEGER,
                    content_package_id INTEGER,
                    payload_json TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(review_queue_id) REFERENCES review_queue(id),
                    FOREIGN KEY(content_package_id) REFERENCES content_packages(id)
                );
                """
            )

    def has_article(self, url: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM raw_articles WHERE source_url = ? OR canonical_url = ? LIMIT 1",
                (url, url),
            ).fetchone()
        return row is not None

    def save_article(self, article: RawArticle, score: ArticleScore) -> None:
        payload = json.dumps(asdict(score), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO raw_articles (
                    source_name,
                    source_category,
                    source_url,
                    canonical_url,
                    title,
                    author,
                    published_at,
                    excerpt,
                    lead_image_url,
                    raw_html,
                    raw_text,
                    word_count,
                    fetched_at,
                    content_hash,
                    score_total,
                    score_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.source_name,
                    article.source_category,
                    article.source_url,
                    article.canonical_url,
                    article.title,
                    article.author,
                    article.published_at.isoformat() if article.published_at else None,
                    article.excerpt,
                    article.lead_image_url,
                    article.raw_html,
                    article.raw_text,
                    article.word_count,
                    article.fetched_at.isoformat() if article.fetched_at else None,
                    hash_text(article.raw_text),
                    score.total_score,
                    payload,
                ),
            )

    def save_generated_package(self, article: RawArticle, package: GeneratedContentPackage) -> int:
        payload = json.dumps(asdict(package), ensure_ascii=False, default=_json_default)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO content_packages (
                    article_url,
                    audience,
                    exercise_profile,
                    optimized_title,
                    summary,
                    teaching_value,
                    reading_passage,
                    keywords_json,
                    discussion_points_json,
                    traceability_notes_json,
                    cover_image_url,
                    generator_provider,
                    generator_model,
                    generation_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.canonical_url,
                    package.audience,
                    package.exercise_profile,
                    package.optimized_title,
                    package.summary,
                    package.teaching_value,
                    package.reading_passage,
                    json.dumps(package.keywords, ensure_ascii=False),
                    json.dumps(package.discussion_points, ensure_ascii=False),
                    json.dumps(package.traceability_notes, ensure_ascii=False),
                    article.lead_image_url,
                    package.generator_provider,
                    package.generator_model,
                    payload,
                ),
            )
            package_id = int(cursor.lastrowid)
            self._save_exercise_sets(connection, package_id, "reading_comprehension", package.reading_questions)
            self._save_exercise_sets(connection, package_id, "cloze_test", package.cloze_questions)
            return package_id

    def enqueue_review_item(
        self,
        item: GeneratedPreviewItem,
        recommendation: str,
        status: str,
        reviewer_note: str = "",
    ) -> int:
        if item.package.package_id is None:
            raise ValueError("Generated package must be persisted before queueing.")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO review_queue (
                    content_package_id,
                    article_url,
                    source_name,
                    audience,
                    exercise_profile,
                    optimized_title,
                    score_total,
                    review_recommendation,
                    status,
                    reviewer_note,
                    approved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.package.package_id,
                    item.preview.article.canonical_url,
                    item.preview.article.source_name,
                    item.package.audience,
                    item.package.exercise_profile,
                    item.package.optimized_title,
                    item.preview.score.total_score,
                    recommendation,
                    status,
                    reviewer_note,
                    utc_now().isoformat() if status == "approved" else None,
                ),
            )
            return int(cursor.lastrowid)

    def list_review_queue(
        self,
        status: str | None = None,
        recommendation: str | None = None,
        limit: int = 50,
    ) -> list[ReviewQueueItem]:
        sql = """
            SELECT
                id,
                content_package_id,
                article_url,
                source_name,
                audience,
                exercise_profile,
                optimized_title,
                score_total,
                review_recommendation,
                status,
                reviewer_note,
                export_directory,
                created_at,
                updated_at,
                approved_at,
                sent_at
            FROM review_queue
        """
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if recommendation:
            clauses.append("review_recommendation = ?")
            params.append(recommendation)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
        return [_row_to_review_item(row) for row in rows]

    def get_review_queue_item(self, queue_id: int) -> ReviewQueueItem | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    content_package_id,
                    article_url,
                    source_name,
                    audience,
                    exercise_profile,
                    optimized_title,
                    score_total,
                    review_recommendation,
                    status,
                    reviewer_note,
                    export_directory,
                    created_at,
                    updated_at,
                    approved_at,
                    sent_at
                FROM review_queue
                WHERE id = ?
                """,
                (queue_id,),
            ).fetchone()
        return _row_to_review_item(row) if row else None

    def get_review_queue_item_by_package_id(self, package_id: int) -> ReviewQueueItem | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    content_package_id,
                    article_url,
                    source_name,
                    audience,
                    exercise_profile,
                    optimized_title,
                    score_total,
                    review_recommendation,
                    status,
                    reviewer_note,
                    export_directory,
                    created_at,
                    updated_at,
                    approved_at,
                    sent_at
                FROM review_queue
                WHERE content_package_id = ?
                """,
                (package_id,),
            ).fetchone()
        return _row_to_review_item(row) if row else None

    def update_review_status(
        self,
        queue_id: int,
        status: str,
        reviewer_note: str | None = None,
        export_directory: str | None = None,
        dingtalk_response: dict[str, object] | None = None,
    ) -> None:
        item = self.get_review_queue_item(queue_id)
        if item is None:
            raise KeyError(f"Unknown review queue item: {queue_id}")
        note = item.reviewer_note if reviewer_note is None else reviewer_note
        export_value = item.export_directory if export_directory is None else export_directory
        approved_at = item.approved_at.isoformat() if item.approved_at else None
        sent_at = item.sent_at.isoformat() if item.sent_at else None
        if status == "approved" and not approved_at:
            approved_at = utc_now().isoformat()
        if status == "sent":
            sent_at = utc_now().isoformat()
            if not approved_at:
                approved_at = utc_now().isoformat()
        response_payload = json.dumps(dingtalk_response, ensure_ascii=False) if dingtalk_response is not None else None
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE review_queue
                SET
                    status = ?,
                    reviewer_note = ?,
                    export_directory = ?,
                    dingtalk_response = COALESCE(?, dingtalk_response),
                    approved_at = ?,
                    sent_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    note,
                    export_value,
                    response_payload,
                    approved_at,
                    sent_at,
                    utc_now().isoformat(),
                    queue_id,
                ),
            )

    def record_delivery_event(
        self,
        channel: str,
        status: str,
        response_payload: dict[str, object],
        queue_id: int | None = None,
        package_id: int | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO delivery_events (
                    review_queue_id,
                    content_package_id,
                    channel,
                    status,
                    response_payload
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    queue_id,
                    package_id,
                    channel,
                    status,
                    json.dumps(response_payload, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def record_activity_log(
        self,
        event_type: str,
        status: str,
        message: str,
        source_name: str = "",
        queue_id: int | None = None,
        package_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO activity_logs (
                    event_type,
                    status,
                    message,
                    source_name,
                    review_queue_id,
                    content_package_id,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    status,
                    message,
                    source_name,
                    queue_id,
                    package_id,
                    json.dumps(payload or {}, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def list_activity_logs(
        self,
        event_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ActivityLogEntry]:
        sql = """
            SELECT
                id,
                event_type,
                status,
                message,
                source_name,
                review_queue_id,
                content_package_id,
                payload_json,
                created_at
            FROM activity_logs
        """
        clauses: list[str] = []
        params: list[object] = []
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
        return [_row_to_activity_log(row) for row in rows]

    def count_activity_logs(
        self,
        event_type: str | None = None,
        status: str | None = None,
    ) -> int:
        sql = "SELECT COUNT(*) FROM activity_logs"
        clauses: list[str] = []
        params: list[object] = []
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._connect() as connection:
            row = connection.execute(sql, tuple(params)).fetchone()
        return int(row[0] if row else 0)

    def count_review_queue_by_status(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*)
                FROM review_queue
                GROUP BY status
                """
            ).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def count_review_queue_by_recommendation(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT review_recommendation, COUNT(*)
                FROM review_queue
                GROUP BY review_recommendation
                """
            ).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def count_delivery_events_for_date(
        self,
        channel: str,
        local_date: str,
        timezone_name: str = "UTC",
    ) -> int:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT created_at
                FROM delivery_events
                WHERE channel = ? AND status = ?
                """,
                (channel, "sent"),
            ).fetchall()
        total = 0
        for row in rows:
            created_at = parse_datetime(row[0])
            if created_at and created_at.astimezone(ZoneInfo(timezone_name)).date().isoformat() == local_date:
                total += 1
        return total

    def get_last_delivery_event(self, channel: str, status: str | None = None) -> DeliveryEvent | None:
        sql = """
            SELECT id, review_queue_id, content_package_id, channel, status, created_at
            FROM delivery_events
            WHERE channel = ?
        """
        params: list[object] = [channel]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(sql, tuple(params)).fetchone()
        return _row_to_delivery_event(row) if row else None

    def load_generated_preview_by_package_id(self, package_id: int) -> GeneratedPreviewItem:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    cp.id,
                    cp.generation_payload,
                    ra.source_name,
                    ra.source_category,
                    ra.source_url,
                    ra.canonical_url,
                    ra.title,
                    ra.author,
                    ra.published_at,
                    ra.excerpt,
                    ra.lead_image_url,
                    ra.raw_html,
                    ra.raw_text,
                    ra.word_count,
                    ra.fetched_at,
                    ra.score_payload
                FROM content_packages cp
                JOIN raw_articles ra ON ra.canonical_url = cp.article_url
                WHERE cp.id = ?
                LIMIT 1
                """,
                (package_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown content package: {package_id}")
        return _row_to_generated_preview(row)

    def load_generated_preview_by_queue_id(self, queue_id: int) -> GeneratedPreviewItem:
        item = self.get_review_queue_item(queue_id)
        if item is None:
            raise KeyError(f"Unknown review queue item: {queue_id}")
        return self.load_generated_preview_by_package_id(item.package_id)

    def _save_exercise_sets(
        self,
        connection: sqlite3.Connection,
        package_id: int,
        exercise_type: str,
        questions: list[object],
    ) -> None:
        connection.execute(
            """
            INSERT INTO exercise_sets (
                content_package_id,
                exercise_type,
                question_payload
            ) VALUES (?, ?, ?)
            """,
            (
                package_id,
                exercise_type,
                json.dumps([asdict(question) for question in questions], ensure_ascii=False),
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA journal_mode=WAL;')
        return conn


def _row_to_review_item(row: sqlite3.Row | tuple[object, ...]) -> ReviewQueueItem:
    return ReviewQueueItem(
        queue_id=int(row[0]),
        package_id=int(row[1]),
        article_url=str(row[2]),
        source_name=str(row[3]),
        audience=str(row[4]),
        exercise_profile=str(row[5]),
        optimized_title=str(row[6]),
        score_total=float(row[7]),
        review_recommendation=str(row[8]),
        status=str(row[9]),
        reviewer_note=str(row[10] or ""),
        export_directory=str(row[11] or ""),
        created_at=parse_datetime(row[12]),
        updated_at=parse_datetime(row[13]),
        approved_at=parse_datetime(row[14]),
        sent_at=parse_datetime(row[15]),
    )


def _row_to_delivery_event(row: sqlite3.Row | tuple[object, ...]) -> DeliveryEvent:
    return DeliveryEvent(
        event_id=int(row[0]),
        queue_id=int(row[1]) if row[1] is not None else None,
        package_id=int(row[2]) if row[2] is not None else None,
        channel=str(row[3]),
        status=str(row[4]),
        created_at=parse_datetime(row[5]),
    )


def _row_to_activity_log(row: sqlite3.Row | tuple[object, ...]) -> ActivityLogEntry:
    payload = json.loads(str(row[7] or "{}"))
    return ActivityLogEntry(
        log_id=int(row[0]),
        event_type=str(row[1]),
        status=str(row[2]),
        message=str(row[3]),
        source_name=str(row[4] or ""),
        queue_id=int(row[5]) if row[5] is not None else None,
        package_id=int(row[6]) if row[6] is not None else None,
        payload=payload if isinstance(payload, dict) else {},
        created_at=parse_datetime(row[8]),
    )


def _row_to_generated_preview(row: sqlite3.Row | tuple[object, ...]) -> GeneratedPreviewItem:
    package_payload = json.loads(str(row[1]))
    score_payload = json.loads(str(row[15] or "{}"))

    article = RawArticle(
        source_name=str(row[2]),
        source_category=str(row[3]),
        source_url=str(row[4]),
        canonical_url=str(row[5]),
        title=str(row[6]),
        author=str(row[7] or ""),
        published_at=parse_datetime(row[8]),
        excerpt=str(row[9] or ""),
        lead_image_url=str(row[10] or ""),
        raw_html=str(row[11] or ""),
        raw_text=str(row[12] or ""),
        word_count=int(row[13] or 0),
        fetched_at=parse_datetime(row[14]),
    )
    score = _score_from_payload(score_payload)
    preview = PreviewItem(
        candidate=ArticleCandidate(
            source_name=article.source_name,
            source_category=article.source_category,
            url=article.source_url,
            title=article.title,
            summary=article.excerpt,
            published_at=article.published_at,
        ),
        article=article,
        score=score,
    )
    package = _package_from_payload(package_payload, package_id=int(row[0]))
    return GeneratedPreviewItem(preview=preview, package=package)


def _score_from_payload(payload: dict[str, object]) -> ArticleScore:
    return ArticleScore(
        freshness_score=float(payload.get("freshness_score", 0.0)),
        interest_score=float(payload.get("interest_score", 0.0)),
        teachability_score=float(payload.get("teachability_score", 0.0)),
        info_density_score=float(payload.get("info_density_score", 0.0)),
        exercise_potential_score=float(payload.get("exercise_potential_score", 0.0)),
        safety_score=float(payload.get("safety_score", 0.0)),
        total_score=float(payload.get("total_score", 0.0)),
        reasons=list(payload.get("reasons", [])),
    )


def _package_from_payload(payload: dict[str, object], package_id: int) -> GeneratedContentPackage:
    return GeneratedContentPackage(
        audience=str(payload["audience"]),
        exercise_profile=str(payload["exercise_profile"]),
        optimized_title=str(payload["optimized_title"]),
        summary=str(payload["summary"]),
        teaching_value=str(payload["teaching_value"]),
        reading_passage=str(payload["reading_passage"]),
        keywords=list(payload.get("keywords", [])),
        discussion_points=list(payload.get("discussion_points", [])),
        reading_questions=[_question_from_payload(item) for item in payload.get("reading_questions", [])],
        cloze_passage=str(payload["cloze_passage"]),
        cloze_questions=[_question_from_payload(item) for item in payload.get("cloze_questions", [])],
        traceability_notes=list(payload.get("traceability_notes", [])),
        task_timings=dict(payload.get("task_timings", {})),
        task_providers=dict(payload.get("task_providers", {})),
        task_models=dict(payload.get("task_models", {})),
        generator_provider=str(payload.get("generator_provider", "")),
        generator_model=str(payload.get("generator_model", "")),
        generated_at=parse_datetime(payload.get("generated_at")) or utc_now(),
        package_id=package_id,
    )


def _question_from_payload(payload: dict[str, object]) -> ExerciseQuestion:
    return ExerciseQuestion(
        question_id=str(payload.get("question_id", "")),
        question_type=str(payload.get("question_type", "")),
        stem=str(payload.get("stem", "")),
        options=list(payload.get("options", [])),
        answer=str(payload.get("answer", "")),
        explanation=str(payload.get("explanation", "")),
    )


def _json_default(value: object) -> str:
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return iso()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")
