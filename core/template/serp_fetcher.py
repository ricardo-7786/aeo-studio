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


def _collect_blog_urls(data: dict, *, limit: int) -> list[str]:
    blocks: list[dict] = []
    for key in ("organic_results", "web_results", "blog_results"):
        raw = data.get(key)
        if isinstance(raw, list):
            blocks.extend(raw)
    views = data.get("views")
    if isinstance(views, dict) and isinstance(views.get("results"), list):
        blocks.extend(views["results"])

    out: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        link = str(block.get("link") or block.get("url") or "").strip()
        if not link or not _is_blog_url(link):
            continue
        if link not in out:
            out.append(link)
        if len(out) >= limit:
            break
    return out


def _serpapi_search(params: dict) -> dict:
    res = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    res.raise_for_status()
    data = res.json()
    if data.get("error"):
        raise ValueError(f"SerpAPI 오류: {data['error']}")
    return data


def fetch_top_blog_urls(
    keyword: str,
    *,
    channel: str = "naver",
    api_key: str,
    limit: int = 3,
) -> list[str]:
    if not api_key:
        raise ValueError("SERPAPI_KEY가 설정되지 않았습니다. .env에 추가하거나 수동 URL을 입력하세요.")
    kw = keyword.strip()
    if not kw:
        raise ValueError("target_keyword가 비어 있습니다.")

    channel = channel.strip().lower()
    if channel not in {"naver", "google"}:
        raise ValueError("channel은 naver 또는 google 이어야 합니다.")

    attempts: list[dict] = []
    if channel == "naver":
        attempts.append(
            {
                "engine": "naver",
                "query": f"{kw} site:blog.naver.com",
                "api_key": api_key,
            }
        )
        attempts.append(
            {
                "engine": "naver",
                "query": kw,
                "api_key": api_key,
            }
        )
        attempts.append(
            {
                "engine": "google",
                "q": f"{kw} site:blog.naver.com",
                "api_key": api_key,
                "google_domain": "google.co.kr",
                "gl": "kr",
                "hl": "ko",
                "num": 10,
            }
        )
    else:
        attempts.append(
            {
                "engine": "google",
                "q": f"{kw} (site:blog.naver.com OR site:tistory.com)",
                "api_key": api_key,
                "google_domain": "google.co.kr",
                "gl": "kr",
                "hl": "ko",
                "num": 10,
            }
        )

    last_error: Exception | None = None
    for params in attempts:
        try:
            data = _serpapi_search(params)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        urls = _collect_blog_urls(data, limit=limit)
        if urls:
            return urls

    if last_error:
        raise last_error
    return []
