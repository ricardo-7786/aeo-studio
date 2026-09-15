"""텔레그램 알림 — 순위 리포트용 (무료 Bot API)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def telegram_config() -> tuple[str, str]:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    return token, chat_id


def telegram_enabled() -> bool:
    token, chat_id = telegram_config()
    return bool(token and chat_id)


def format_rank_telegram(
    results: list[dict[str, Any]],
    *,
    excel_name: str = "",
    brand: str = "OMA",
) -> str:
    """텔레그램용 — 원장이 바로 읽히는 쉬운 요약."""
    from datetime import date

    urgent = [r for r in results if r.get("action") == "1순위_즉시대응"]
    weekly = [r for r in results if r.get("action") == "주간_2~3편후보"]
    ok_list = [
        r
        for r in results
        if r.get("exposed") == "O"
        and r.get("action") not in {"1순위_즉시대응", "주간_2~3편후보", "재실행"}
    ]
    hidden = [r for r in results if r.get("exposed") == "X"]

    lines = [
        f"[{brand}]",
        "네이버 플레이스 순위 주간 점검",
        f"날짜 {date.today().isoformat()} · 키워드 {len(results)}개",
        "",
        "※ 이건 블로그 순위가 아니라,",
        "   지도/플레이스에 학원이 보이는지 본 결과입니다.",
        "",
    ]

    lines.append("—— 지금 손볼 것 ——")
    if urgent:
        lines.append("① 우선 대응 (대표 키워드가 약함)")
        lines.append("   → 플레이스 소식·사진·리뷰 보강, 또는 관련 글 리뉴얼")
        for r in urgent[:10]:
            lines.append(f"   · {r.get('keyword')}: {r.get('rank')}")
        lines.append("")
    else:
        lines.append("① 우선 대응: 없음")
        lines.append("")

    if weekly:
        lines.append("② 이번 주~여유 있을 때 (글 1~2편이면 충분)")
        for r in weekly[:8]:
            lines.append(f"   · {r.get('keyword')}: {r.get('rank')}")
        lines.append("")
    else:
        lines.append("② 여유 후보: 없음")
        lines.append("")

    lines.append("—— 괜찮은 것 ——")
    if ok_list:
        lines.append("플레이스에 잘 보이는 키워드")
        for r in ok_list[:10]:
            lines.append(f"   · {r.get('keyword')}: {r.get('rank')}")
    else:
        lines.append("해당 없음")
    lines.append("")

    if hidden and not urgent:
        lines.append("—— 안 보인 키워드 ——")
        for r in hidden[:8]:
            lines.append(f"   · {r.get('keyword')}: {r.get('rank')}")
        lines.append("")

    lines.append("—— 다음에 할 일 ——")
    if urgent:
        lines.append("1) 위 ① 키워드부터 처리")
        lines.append("2) 자세한 캡처는 GitHub Actions 결과물(Artifacts) 또는 맥 /ranks")
    else:
        lines.append("급할 건 없습니다. 주 1회 점검만 유지하세요.")
    if excel_name:
        lines.append(f"(파일명: {excel_name})")

    text = "\n".join(lines)
    return text[:4000]


def send_telegram_message(
    text: str,
    *,
    token: str = "",
    chat_id: str = "",
    parse_mode: str = "",
) -> dict[str, Any]:
    token = token or telegram_config()[0]
    chat_id = chat_id or telegram_config()[1]
    if not token or not chat_id:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        res = requests.post(url, json=payload, timeout=20)
        data = res.json() if res.content else {}
        if res.status_code != 200 or not data.get("ok"):
            return {
                "ok": False,
                "error": data.get("description") or res.text[:200] or f"HTTP {res.status_code}",
            }
        return {"ok": True, "result": data.get("result")}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)[:200]}


def notify_rank_results(
    results: list[dict[str, Any]],
    *,
    excel_name: str = "",
    brand: str = "OMA실용음악학원",
) -> dict[str, Any]:
    if not telegram_enabled():
        return {"ok": False, "skipped": True, "error": "텔레그램 미설정"}
    text = format_rank_telegram(results, excel_name=excel_name, brand=brand)
    return send_telegram_message(text)
