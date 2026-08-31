"""CODA(Postgres) 읽기 전용 연결 — AEO DB와 분리."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_coda_database_url() -> str:
    return (os.getenv("CODA_DATABASE_URL") or os.getenv("CODA_DIRECT_URL") or "").strip()


def is_coda_db_configured() -> bool:
    return bool(get_coda_database_url())


def connect_coda():
    import psycopg

    url = get_coda_database_url()
    if not url:
        raise RuntimeError(
            "CODA_DATABASE_URL이 설정되지 않았습니다. CODA(Supabase) Postgres 연결 문자열을 .env에 추가하세요."
        )
    kwargs: dict = {}
    if any(x in url for x in ("supabase", "sslmode=require", "render.com")):
        kwargs["sslmode"] = "require"
    return psycopg.connect(url, **kwargs)
