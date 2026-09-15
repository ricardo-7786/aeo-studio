#!/usr/bin/env python3
"""macOS launchd — 주 1회 순위 점검+텔레그램 스케줄 설치/해제.

.env 예:
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
  RANK_SCHEDULE_WEEKDAY=mon   # mon..sun 또는 0(일)~6(토)
  RANK_SCHEDULE_HOUR=9
  RANK_SCHEDULE_MINUTE=0
  RANK_SCHEDULE_LIMIT=0       # 0=키워드 전체

사용:
  .venv/bin/python scripts/setup_rank_schedule.py --install
  .venv/bin/python scripts/setup_rank_schedule.py --status
  .venv/bin/python scripts/setup_rank_schedule.py --uninstall
"""

from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

LABEL = "com.aeo.rank-weekly"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"

WEEKDAY_MAP = {
    "sun": 0,
    "sunday": 0,
    "mon": 1,
    "monday": 1,
    "tue": 2,
    "tuesday": 2,
    "wed": 3,
    "wednesday": 3,
    "thu": 4,
    "thursday": 4,
    "fri": 5,
    "friday": 5,
    "sat": 6,
    "saturday": 6,
}
WEEKDAY_LABEL = {
    0: "일",
    1: "월",
    2: "화",
    3: "수",
    4: "목",
    5: "금",
    6: "토",
}


def _parse_weekday(raw: str) -> int:
    s = (raw or "mon").strip().lower()
    if s.isdigit():
        n = int(s)
        if 0 <= n <= 7:
            return 0 if n == 7 else n
    if s in WEEKDAY_MAP:
        return WEEKDAY_MAP[s]
    raise SystemExit(f"RANK_SCHEDULE_WEEKDAY 잘못됨: {raw} (예: mon, fri, 1)")


def _python_bin() -> Path:
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.is_file():
        return venv
    return Path(sys.executable)


def schedule_from_env() -> dict:
    weekday = _parse_weekday(os.getenv("RANK_SCHEDULE_WEEKDAY", "mon"))
    hour = int(os.getenv("RANK_SCHEDULE_HOUR", "9") or 9)
    minute = int(os.getenv("RANK_SCHEDULE_MINUTE", "0") or 0)
    limit = (os.getenv("RANK_SCHEDULE_LIMIT") or "0").strip()
    return {
        "weekday": weekday,
        "hour": max(0, min(23, hour)),
        "minute": max(0, min(59, minute)),
        "limit": limit,
    }


def build_plist() -> dict:
    sch = schedule_from_env()
    py = str(_python_bin())
    job = str(ROOT / "scripts" / "rank_weekly_job.py")
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    args = [py, job]
    if sch["limit"].isdigit() and int(sch["limit"]) > 0:
        args += ["--limit", sch["limit"]]

    return {
        "Label": LABEL,
        "WorkingDirectory": str(ROOT),
        "ProgramArguments": args,
        "StartCalendarInterval": {
            "Weekday": sch["weekday"],
            "Hour": sch["hour"],
            "Minute": sch["minute"],
        },
        "StandardOutPath": str(log_dir / "rank_weekly.out.log"),
        "StandardErrorPath": str(log_dir / "rank_weekly.err.log"),
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
            "LANG": "ko_KR.UTF-8",
        },
    }


def install() -> None:
    from core.telegram_notify import telegram_enabled

    if not telegram_enabled():
        print("경고: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없습니다. 알림이 실패합니다.")
        print("      .env에 넣은 뒤 다시 --install 하세요.")

    plist = build_plist()
    sch = schedule_from_env()
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 기존 unload
    if PLIST_PATH.exists():
        subprocess.run(
            ["launchctl", "unload", str(PLIST_PATH)],
            check=False,
            capture_output=True,
        )

    with PLIST_PATH.open("wb") as f:
        plistlib.dump(plist, f)

    r = subprocess.run(
        ["launchctl", "load", str(PLIST_PATH)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        raise SystemExit("launchctl load 실패")

    print("설치 완료:", PLIST_PATH)
    print(
        f"스케줄: 매주 {WEEKDAY_LABEL[sch['weekday']]}요일 "
        f"{sch['hour']:02d}:{sch['minute']:02d}"
    )
    print("잡 스크립트:", ROOT / "scripts" / "rank_weekly_job.py")
    print("로그:", ROOT / "logs" / "rank_weekly.out.log")
    print("Mac이 켜져 있고 깨어 있어야 실행됩니다 (절전 중이면 밀릴 수 있음).")


def uninstall() -> None:
    if PLIST_PATH.exists():
        subprocess.run(
            ["launchctl", "unload", str(PLIST_PATH)],
            check=False,
            capture_output=True,
        )
        PLIST_PATH.unlink(missing_ok=True)
        print("해제 완료:", PLIST_PATH)
    else:
        print("설치된 스케줄 없음")


def status() -> None:
    sch = schedule_from_env()
    exists = PLIST_PATH.exists()
    print(f"plist: {'있음' if exists else '없음'} — {PLIST_PATH}")
    print(
        f".env 스케줄: 매주 {WEEKDAY_LABEL[sch['weekday']]} "
        f"{sch['hour']:02d}:{sch['minute']:02d} / limit={sch['limit'] or '전체'}"
    )
    if exists:
        r = subprocess.run(
            ["launchctl", "list", LABEL],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            print("launchctl:", r.stdout.strip() or "(등록됨)")
        else:
            print("launchctl: 미로드 — --install 다시 실행하세요")


def main() -> int:
    if sys.platform != "darwin":
        print("이 스케줄 설치는 macOS launchd 전용입니다.")
        print("Linux면 cron 예:")
        print(
            f'  0 9 * * 1 cd "{ROOT}" && .venv/bin/python scripts/rank_weekly_job.py'
        )
        return 1

    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--install", action="store_true")
    g.add_argument("--uninstall", action="store_true")
    g.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.install:
        install()
    elif args.uninstall:
        uninstall()
    else:
        status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
