"""생성 초안 DB 저장 — aeo_drafts 테이블."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from db.connection import get_connection


@dataclass(frozen=True)
class DraftRow:
    id: str
    academy_key: str
    lesson_title: str
    source_text: str
    tistory_markdown: str
    tistory_json_ld: dict[str, Any]
    naver_title: str
    naver_body: str
    naver_keywords: list[str]
    generated_at: datetime


def _row_from_record(rec: tuple[Any, ...]) -> DraftRow:
    json_ld = rec[5] if isinstance(rec[5], dict) else json.loads(rec[5] or "{}")
    keywords = list(rec[8] or [])
    return DraftRow(
        id=str(rec[0]),
        academy_key=rec[1],
        lesson_title=rec[2] or "",
        source_text=rec[3] or "",
        tistory_markdown=rec[4] or "",
        tistory_json_ld=json_ld,
        naver_title=rec[6] or "",
        naver_body=rec[7] or "",
        naver_keywords=keywords,
        generated_at=rec[9],
    )


_SELECT = """
SELECT id::text, academy_key, lesson_title, source_text,
       tistory_markdown, tistory_json_ld, naver_title, naver_body,
       naver_keywords, generated_at
FROM aeo_drafts
"""


def save_aeo_draft(
    *,
    business_key: str,
    lesson_title: str,
    source_text: str,
    tistory_markdown: str,
    json_ld: dict[str, Any],
    naver_title: str,
    naver_body: str,
    naver_keywords: list[str],
    stt_snippets: list[dict[str, Any]] | None = None,
) -> str:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO aeo_drafts (
                  academy_key, lesson_title, source_text,
                  tistory_markdown, tistory_json_ld,
                  naver_title, naver_body, naver_keywords,
                  stt_snippets, generated_at
                ) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb, CURRENT_TIMESTAMP)
                RETURNING id::text
                """,
                (
                    business_key,
                    lesson_title,
                    source_text,
                    tistory_markdown,
                    json.dumps(json_ld, ensure_ascii=False),
                    naver_title,
                    naver_body,
                    naver_keywords,
                    json.dumps(stt_snippets or [], ensure_ascii=False),
                ),
            )
            draft_id = cur.fetchone()[0]
        conn.commit()
    return draft_id


def get_draft(draft_id: str) -> DraftRow | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"{_SELECT} WHERE id = %s::uuid", (draft_id.strip(),))
            rec = cur.fetchone()
    return _row_from_record(rec) if rec else None


def list_drafts(*, business_key: str | None = None, limit: int = 50) -> list[DraftRow]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if business_key:
                cur.execute(
                    f"{_SELECT} WHERE academy_key = %s ORDER BY generated_at DESC LIMIT %s",
                    (business_key.strip(), limit),
                )
            else:
                cur.execute(
                    f"{_SELECT} ORDER BY generated_at DESC LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()
    return [_row_from_record(r) for r in rows]
