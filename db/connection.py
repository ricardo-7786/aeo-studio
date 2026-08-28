"""PostgreSQL 연결 — DATABASE_URL 또는 DIRECT_URL."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def get_database_url() -> str:
    return (os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL") or "").strip()


def is_db_configured() -> bool:
    return bool(get_database_url())


@lru_cache(maxsize=1)
def get_connection():
    import psycopg

    url = get_database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL이 설정되지 않았습니다. .env에 PostgreSQL 연결 문자열을 추가하세요."
        )
    return psycopg.connect(url)
