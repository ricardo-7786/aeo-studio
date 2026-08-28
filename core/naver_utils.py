"""네이버 SEO 지역 키워드 — 업종 범용."""

from __future__ import annotations

import re

from config.industry import INDUSTRY_META, normalize_industry
from config.settings import AcademyProfile


def build_naver_local_keywords(academy: AcademyProfile) -> list[str]:
    blob = f"{academy.location} {academy.address}".strip()
    industry = normalize_industry(getattr(academy, "industry", "general"))
    meta = INDUSTRY_META[industry]
    primary = (academy.services[0] if academy.services else meta["entity"]).strip() or meta["entity"]

    station_match = re.search(r"([가-힣A-Za-z0-9]+역)", blob)
    city_match = re.search(
        r"(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|[가-힣]+시|[가-힣]+군)",
        blob,
    )
    district_match = re.search(r"([가-힣]+구)", blob)

    station = station_match.group(1) if station_match else ""
    city_raw = city_match.group(1) if city_match else ""
    city = (
        city_raw.replace("특별시", "시")
        .replace("광역시", "시")
        .replace("특별자치시", "시")
    )
    place_short = ""
    if station:
        place_short = station.replace("역", "")
    elif district_match:
        place_short = district_match.group(1).replace("구", "")

    out: list[str] = []

    def push(s: str) -> None:
        t = re.sub(r"\s+", " ", s).strip()
        if t and t not in out:
            out.append(t)

    suffix = {
        "education": "학원",
        "restaurant": "맛집",
        "clinic": "클리닉",
        "fitness": "센터",
        "beauty": "샵",
        "general": "",
    }.get(industry, "")

    if station:
        push(f"{station} {primary}{suffix}".strip())
    if city:
        push(f"{city} {primary}")
    if place_short:
        push(f"{place_short} {primary}")
    if place_short and academy.name:
        push(f"{place_short} {academy.name.strip()}")
    if academy.name and primary:
        push(f"{academy.name} {primary}")

    if not out:
        push(f"{academy.name} {primary}")
        push(f"{primary} 후기")
        if suffix:
            push(f"{primary}{suffix}")

    return out[:6]


def normalize_naver_title(raw: str, fallback: str) -> str:
    t = re.sub(r"\s+", " ", (raw or "").strip()) or fallback
    max_len = 58
    if len(t) <= max_len:
        return t
    cut = t[:max_len]
    break_at = max(
        cut.rfind(" "),
        cut.rfind("|"),
        cut.rfind("—"),
        cut.rfind("-"),
        cut.rfind(","),
        cut.rfind(":"),
    )
    if break_at >= 24:
        return cut[:break_at].strip()
    return cut.strip()


def strip_naver_markdown(raw: str) -> str:
    s = raw.replace("\r\n", "\n")

    def link_repl(m: re.Match[str]) -> str:
        label, url = m.group(1).strip(), m.group(2)
        if re.match(r"^사진\s*추천\s*:", label, re.I):
            return f"[{label}]"
        return f"{label} {url}".strip()

    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", link_repl, s)
    s = re.sub(r"^#{1,6}\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
