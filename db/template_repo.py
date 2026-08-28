"""aeo_templates 테이블 CRUD + 캐시."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from db.connection import get_connection


@dataclass(frozen=True)
class TemplateRow:
    id: str
    target_keyword: str
    channel: str
    source_urls: list[str]
    template_json: dict[str, Any]
    raw_extractions: list[dict[str, Any]]
    fetched_at: datetime


def _normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.strip().split())


def get_cached_template(
    keyword: str,
    channel: str,
    *,
    max_age_hours: int = 72,
) -> TemplateRow | None:
    key = _normalize_keyword(keyword)
    ch = channel.strip().lower()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, target_keyword, channel, source_urls,
                       template_json, raw_extractions, fetched_at
                FROM aeo_templates
                WHERE target_keyword = %s AND channel = %s AND fetched_at >= %s
                """,
                (key, ch, cutoff.replace(tzinfo=None)),
            )
            rec = cur.fetchone()
    if not rec:
        return None
    return TemplateRow(
        id=rec[0],
        target_keyword=rec[1],
        channel=rec[2],
        source_urls=list(rec[3] or []),
        template_json=rec[4] if isinstance(rec[4], dict) else json.loads(rec[4] or "{}"),
        raw_extractions=rec[5] if isinstance(rec[5], list) else json.loads(rec[5] or "[]"),
        fetched_at=rec[6],
    )


def upsert_template(
    *,
    keyword: str,
    channel: str,
    source_urls: list[str],
    template_json: dict[str, Any],
    raw_extractions: list[dict[str, Any]],
) -> str:
    key = _normalize_keyword(keyword)
    ch = channel.strip().lower()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO aeo_templates (
                  target_keyword, channel, source_urls, template_json, raw_extractions, fetched_at
                ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (target_keyword, channel) DO UPDATE SET
                  source_urls = EXCLUDED.source_urls,
                  template_json = EXCLUDED.template_json,
                  raw_extractions = EXCLUDED.raw_extractions,
                  fetched_at = CURRENT_TIMESTAMP
                RETURNING id::text
                """,
                (
                    key,
                    ch,
                    source_urls,
                    json.dumps(template_json, ensure_ascii=False),
                    json.dumps(raw_extractions, ensure_ascii=False),
                ),
            )
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id


def list_templates(*, limit: int = 50) -> list[TemplateRow]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, target_keyword, channel, source_urls,
                       template_json, raw_extractions, fetched_at
                FROM aeo_templates
                ORDER BY fetched_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    out: list[TemplateRow] = []
    for rec in rows:
        out.append(
            TemplateRow(
                id=rec[0],
                target_keyword=rec[1],
                channel=rec[2],
                source_urls=list(rec[3] or []),
                template_json=rec[4] if isinstance(rec[4], dict) else json.loads(rec[4] or "{}"),
                raw_extractions=rec[5] if isinstance(rec[5], list) else json.loads(rec[5] or "[]"),
                fetched_at=rec[6],
            )
        )
    return out
