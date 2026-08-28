"""발행 URL·순위 추적 — published_posts 테이블."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from db.connection import get_connection


@dataclass(frozen=True)
class PublishedPostRow:
    id: str
    draft_id: str | None
    academy_key: str
    channel: str
    published_url: str
    target_keyword: str
    target_engine: str
    current_rank: int | None
    previous_rank: int | None
    last_checked_at: datetime | None
    is_monitored: bool
    created_at: datetime


def _row_from_record(rec: tuple[Any, ...]) -> PublishedPostRow:
    return PublishedPostRow(
        id=str(rec[0]),
        draft_id=str(rec[1]) if rec[1] else None,
        academy_key=rec[2],
        channel=rec[3],
        published_url=rec[4],
        target_keyword=rec[5] or "",
        target_engine=rec[6] or "naver",
        current_rank=rec[7],
        previous_rank=rec[8],
        last_checked_at=rec[9],
        is_monitored=bool(rec[10]),
        created_at=rec[11],
    )


_SELECT = """
SELECT id::text, draft_id::text, academy_key, channel, published_url,
       target_keyword, target_engine, current_rank, previous_rank,
       last_checked_at, is_monitored, created_at
FROM published_posts
"""


def register_published_post(
    *,
    business_key: str,
    channel: str,
    published_url: str,
    target_keyword: str = "",
    target_engine: str = "naver",
    draft_id: str | None = None,
    is_monitored: bool = True,
) -> str:
    channel = channel.strip().lower()
    if channel not in {"naver", "tistory", "wordpress"}:
        raise ValueError("channel은 naver, tistory, wordpress 중 하나여야 합니다.")
    engine = (target_engine or "naver").strip().lower()
    if engine not in {"naver", "google"}:
        raise ValueError("target_engine은 naver 또는 google 이어야 합니다.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO published_posts (
                  draft_id, academy_key, channel, published_url,
                  target_keyword, target_engine, is_monitored
                ) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (
                    draft_id,
                    business_key.strip(),
                    channel,
                    published_url.strip(),
                    target_keyword.strip(),
                    engine,
                    is_monitored,
                ),
            )
            post_id = cur.fetchone()[0]
        conn.commit()
    return post_id


def list_published_posts(
    *,
    business_key: str | None = None,
    limit: int = 100,
) -> list[PublishedPostRow]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if business_key:
                cur.execute(
                    f"{_SELECT} WHERE academy_key = %s ORDER BY created_at DESC LIMIT %s",
                    (business_key.strip(), limit),
                )
            else:
                cur.execute(
                    f"{_SELECT} ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()
    return [_row_from_record(r) for r in rows]


def get_published_post(post_id: str) -> PublishedPostRow | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"{_SELECT} WHERE id = %s::uuid", (post_id.strip(),))
            rec = cur.fetchone()
    return _row_from_record(rec) if rec else None
