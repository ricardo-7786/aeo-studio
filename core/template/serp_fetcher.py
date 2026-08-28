"""SerpAPI — 키워드별 상위 블로그 URL 수집."""

from __future__ import annotations

import re

import requests

BLOG_HOST_PATTERNS = (
    r"blog\.naver\.com",
    r"m\.blog\.naver\.com",
    r"tistory\.com",
    r"brunch\.co\.kr",
    r"post\.naver\.com",
)


def _is_blog_url(url: str) -> bool:
    return any(re.search(p, url, re.I) for p in BLOG_HOST_PATTERNS)


def fetch_top_blog_urls(
    keyword: str,
    *,
    channel: str = "naver",
    api_key: str,
    limit: int = 3,
) -> list[str]:
    if not api_key:
        raise ValueError("SERPAPI_KEY가 설정되지 않았습니다. .env에 추가하거나 수동 URL을 입력하세요.")
    if not keyword.strip():
        raise ValueError("target_keyword가 비어 있습니다.")

    channel = channel.strip().lower()
    if channel == "naver":
        params = {
            "engine": "naver",
            "query": keyword.strip(),
            "api_key": api_key,
        }
    elif channel == "google":
        params = {
            "engine": "google",
            "q": keyword.strip(),
            "api_key": api_key,
            "google_domain": "google.co.kr",
            "gl": "kr",
            "hl": "ko",
            "num": 10,
        }
    else:
        raise ValueError("channel은 naver 또는 google 이어야 합니다.")

    res = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    res.raise_for_status()
    data = res.json()

    candidates: list[str] = []
    if channel == "naver":
        for block in data.get("organic_results", []):
            link = str(block.get("link") or "").strip()
            if link and _is_blog_url(link):
                candidates.append(link)
        for block in data.get("views", {}).get("results", []):
            link = str(block.get("link") or "").strip()
            if link and _is_blog_url(link):
                candidates.append(link)
    else:
        for block in data.get("organic_results", []):
            link = str(block.get("link") or "").strip()
            if link and _is_blog_url(link):
                candidates.append(link)

    out: list[str] = []
    for url in candidates:
        if url not in out:
            out.append(url)
        if len(out) >= limit:
            break
    return out
