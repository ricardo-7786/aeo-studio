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
    """텔레그램용 짧은 요약 (4096자 제한 대비)."""
    from datetime import date

    exposed = sum(1 for r in results if r.get("exposed") == "O")
    hidden = sum(1 for r in results if r.get("exposed") == "X")
    urgent = [r for r in results if r.get("action") == "1순위_즉시대응"]
    weekly = [r for r in results if r.get("action") == "주간_2~3편후보"]

    lines = [
        f"📍 {brand} 플레이스 순위 점검",
        f"날짜: {date.today().isoformat()}",
        f"전체 {len(results)} · 노출 O {exposed} · X {hidden}",
        f"즉시대응 {len(urgent)} · 주간후보 {len(weekly)}",
        "",
    ]
    if urgent:
        lines.append("🚨 즉시대응")
        for r in urgent[:12]:
            conf = r.get("confidence") or ""
            lines.append(
                f"· {r.get('keyword')} — {r.get('rank')}"
                + (f" ({conf})" if conf else "")
            )
        if len(urgent) > 12:
            lines.append(f"· …외 {len(urgent) - 12}개")
        lines.append("")
    if weekly:
        lines.append("📝 주간 후보 (상위)")
        for r in weekly[:8]:
            lines.append(f"· {r.get('keyword')} — {r.get('rank')}")
        lines.append("")

    lines.append("유지/관찰")
    for r in results:
        if r.get("action") in {"1순위_즉시대응", "주간_2~3편후보", "재실행"}:
            continue
        if r.get("exposed") == "O":
            lines.append(f"· {r.get('keyword')} — {r.get('rank')}")
    if excel_name:
        lines.append("")
        lines.append(f"엑셀: {excel_name}")
    lines.append("")
    lines.append("웹: /ranks 에서 캡처·리뉴얼 확인")
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
