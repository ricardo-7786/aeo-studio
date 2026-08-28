#!/usr/bin/env python3
"""DB 마이그레이션 실행 — migrations/*.sql 순서대로 적용."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.connection import get_connection, get_database_url, is_db_configured  # noqa: E402

MIGRATIONS = [
    "001_academy_aeo_profiles.sql",
    "002_drafts_and_rank_tracking.sql",
    "003_businesses.sql",
    "004_aeo_templates.sql",
]


def main() -> int:
    if not is_db_configured():
        print("[ERROR] DATABASE_URL 또는 DIRECT_URL을 .env에 설정하세요.", file=sys.stderr)
        return 1

    print(f"DB: {get_database_url().split('@')[-1] if '@' in get_database_url() else '(local)'}")
    mig_dir = ROOT / "migrations"

    with get_connection() as conn:
        for name in MIGRATIONS:
            path = mig_dir / name
            if not path.is_file():
                print(f"  skip (missing): {name}")
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
                print(f"  applied: {name}")
            except Exception as exc:
                conn.rollback()
                # 001 users FK 등 레거시 실패는 경고만
                if name == "001_academy_aeo_profiles.sql":
                    print(f"  warn: {name} — {exc} (003_businesses.sql 시드로 대체 가능)")
                else:
                    print(f"  FAILED: {name} — {exc}", file=sys.stderr)
                    return 1

    print("마이그레이션 완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
