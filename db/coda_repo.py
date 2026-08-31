"""CODA DB — 레sson·녹음·태그 읽기 (읽기 전용)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from db.coda_connection import connect_coda, is_coda_db_configured


@dataclass
class CodaLessonRow:
    lesson_id: int
    title: str
    teacher_name: str
    student_name: str
    key_coaching_points: str
    summary: str
    created_at: datetime | None
    recording_count: int


@dataclass
class CodaRecordingRow:
    recording_id: int
    title: str
    audio_url: str
    processing_status: str
    created_at: datetime | None


@dataclass
class CodaTagRow:
    timestamp_ms: int
    type: str
    note: str


@dataclass
class CodaLessonBundle:
    lesson: CodaLessonRow
    recordings: list[CodaRecordingRow]
    tags: list[CodaTagRow]


def list_lessons(
    *,
    teacher_name: str = "",
    limit: int = 40,
) -> list[CodaLessonRow]:
    if not is_coda_db_configured():
        return []

    teacher_filter = teacher_name.strip()
    sql = """
        SELECT
            l.id AS lesson_id,
            COALESCE(l.title, '') AS title,
            COALESCE(t.full_name, '') AS teacher_name,
            COALESCE(s.full_name, '') AS student_name,
            COALESCE(l.key_coaching_points, '') AS key_coaching_points,
            COALESCE(l.summary, '') AS summary,
            l.created_at,
            COUNT(lr.id) FILTER (WHERE lr.audio_url IS NOT NULL AND lr.audio_url <> '') AS recording_count
        FROM lessons l
        JOIN users s ON s.id = l.student_id
        LEFT JOIN users t ON t.id = l.teacher_id
        LEFT JOIN lesson_recordings lr ON lr.lesson_id = l.id
        WHERE (%s = '' OR t.full_name ILIKE '%%' || %s || '%%')
        GROUP BY l.id, l.title, t.full_name, s.full_name, l.key_coaching_points, l.summary, l.created_at
        HAVING COUNT(lr.id) FILTER (WHERE lr.audio_url IS NOT NULL AND lr.audio_url <> '') > 0
        ORDER BY l.created_at DESC NULLS LAST, l.id DESC
        LIMIT %s
    """
    with connect_coda() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (teacher_filter, teacher_filter, limit))
            rows = cur.fetchall()

    out: list[CodaLessonRow] = []
    for row in rows:
        out.append(
            CodaLessonRow(
                lesson_id=int(row[0]),
                title=str(row[1] or ""),
                teacher_name=str(row[2] or ""),
                student_name=str(row[3] or ""),
                key_coaching_points=str(row[4] or ""),
                summary=str(row[5] or ""),
                created_at=row[6],
                recording_count=int(row[7] or 0),
            )
        )
    return out


def get_lesson_bundle(lesson_id: int) -> CodaLessonBundle | None:
    if not is_coda_db_configured():
        return None

    lesson_sql = """
        SELECT
            l.id,
            COALESCE(l.title, ''),
            COALESCE(t.full_name, ''),
            COALESCE(s.full_name, ''),
            COALESCE(l.key_coaching_points, ''),
            COALESCE(l.summary, ''),
            l.created_at
        FROM lessons l
        JOIN users s ON s.id = l.student_id
        LEFT JOIN users t ON t.id = l.teacher_id
        WHERE l.id = %s
    """
    rec_sql = """
        SELECT id, COALESCE(title, ''), COALESCE(audio_url, ''),
               COALESCE(processing_status, 'ready'), created_at
        FROM lesson_recordings
        WHERE lesson_id = %s AND audio_url IS NOT NULL AND audio_url <> ''
        ORDER BY created_at ASC NULLS LAST, id ASC
    """
    tag_sql = """
        SELECT COALESCE(timestamp_ms, 0), COALESCE(type, ''), COALESCE(note, '')
        FROM tags
        WHERE lesson_id = %s
        ORDER BY timestamp_ms ASC NULLS LAST, id ASC
    """

    with connect_coda() as conn:
        with conn.cursor() as cur:
            cur.execute(lesson_sql, (lesson_id,))
            lesson_row = cur.fetchone()
            if not lesson_row:
                return None

            cur.execute(rec_sql, (lesson_id,))
            rec_rows = cur.fetchall()

        tag_rows: list = []
        try:
            with conn.cursor() as cur:
                cur.execute(tag_sql, (lesson_id,))
                tag_rows = cur.fetchall()
        except Exception:  # noqa: BLE001
            conn.rollback()

    lesson = CodaLessonRow(
        lesson_id=int(lesson_row[0]),
        title=str(lesson_row[1] or ""),
        teacher_name=str(lesson_row[2] or ""),
        student_name=str(lesson_row[3] or ""),
        key_coaching_points=str(lesson_row[4] or ""),
        summary=str(lesson_row[5] or ""),
        created_at=lesson_row[6],
        recording_count=len(rec_rows),
    )
    recordings = [
        CodaRecordingRow(
            recording_id=int(r[0]),
            title=str(r[1] or ""),
            audio_url=str(r[2] or ""),
            processing_status=str(r[3] or "ready"),
            created_at=r[4],
        )
        for r in rec_rows
    ]
    tags = [
        CodaTagRow(timestamp_ms=int(t[0]), type=str(t[1] or ""), note=str(t[2] or ""))
        for t in tag_rows
    ]
    return CodaLessonBundle(lesson=lesson, recordings=recordings, tags=tags)
