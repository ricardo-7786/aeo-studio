#!/usr/bin/env python3
"""주간 순위 점검 잡 — 점검 후 텔레그램 요약 전송.

수동 실행:
  .venv/bin/python scripts/rank_weekly_job.py
  .venv/bin/python scripts/rank_weekly_job.py --limit 10

스케줄 설치(macOS launchd):
  .venv/bin/python scripts/setup_rank_schedule.py --install
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    from scripts.naver_place_rank import BRAND_MAIN, KEYWORDS, run_check, save_excel
    from core.telegram_notify import notify_rank_results, telegram_enabled

    parser = argparse.ArgumentParser(description="주간 순위 점검 + 텔레그램")
    parser.add_argument("--limit", type=int, default=0, help="0=전체, N=앞에서 N개")
    parser.add_argument(
        "--channel",
        type=str,
        default=os.getenv("RANK_BROWSER_CHANNEL", "chrome"),
        choices=("chrome", "chromium", "msedge"),
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="텔레그램 없이 점검만",
    )
    args = parser.parse_args()

    env_limit = (os.getenv("RANK_SCHEDULE_LIMIT") or "").strip()
    limit = args.limit
    if limit <= 0 and env_limit.isdigit():
        limit = int(env_limit)

    keywords = KEYWORDS[:limit] if limit > 0 else list(KEYWORDS)
    today = date.today().isoformat()
    out_dir = ROOT / "captures" / today
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    print(f"[rank_weekly_job] {today} keywords={len(keywords)} channel={args.channel}")

    results = run_check(
        keywords=keywords,
        out_dir=out_dir,
        headed=False,
        delay_min=float(os.getenv("RANK_DELAY_MIN", "2") or 2),
        delay_max=float(os.getenv("RANK_DELAY_MAX", "4") or 4),
        channel=args.channel,
    )
    xlsx = ROOT / f"rank_result_{today}.xlsx"
    save_excel(results, xlsx)
    print(f"엑셀: {xlsx}")

    if args.no_telegram:
        print("텔레그램 스킵 (--no-telegram)")
        return 0

    if not telegram_enabled():
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 — 알림 불가")
        return 2

    out = notify_rank_results(results, excel_name=xlsx.name, brand=BRAND_MAIN)
    if out.get("ok"):
        print("텔레그램 전송 완료")
        return 0
    print(f"텔레그램 실패: {out.get('error')}")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
