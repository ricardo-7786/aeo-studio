"""블로그 URL → 제목·소제목·글자 수·Q&A 패턴 추출 (requests + BeautifulSoup)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from core.template.models import PostStructure

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

QUESTION_RE = re.compile(r"(^.+\?\s*$|^Q[\.\:].+|^질문[\:\.]?\s*.+)", re.M | re.I)


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def _extract_headings(soup: BeautifulSoup) -> list[str]:
    headings: list[str] = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        t = _clean_text(tag.get_text(" ", strip=True))
        if t and t not in headings:
            headings.append(t)
    return headings[:20]


def _extract_body_text(soup: BeautifulSoup) -> str:
    for sel in (
        "div.se-main-container",
        "div#postViewArea",
        "div.post-view",
        "article",
        "main",
        "div.entry-content",
        "div.tt_article_useless_p_margin",
    ):
        node = soup.select_one(sel)
        if node:
            return _clean_text(node.get_text("\n", strip=True))
    body = soup.body or soup
    return _clean_text(body.get_text("\n", strip=True))


def _guess_qa_patterns(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: list[str] = []
    for line in lines:
        if QUESTION_RE.match(line) and line not in out:
            out.append(line[:120])
        if len(out) >= 8:
            break
    return out


def extract_post_structure(url: str, *, timeout: int = 20) -> PostStructure:
    res = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"},
    )
    res.raise_for_status()
    res.encoding = res.encoding or "utf-8"
    soup = BeautifulSoup(res.text, "lxml")

    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = _clean_text(og["content"])
    if not title and soup.title:
        title = _clean_text(soup.title.get_text())

    body = _extract_body_text(soup)
    headings = _extract_headings(soup)
    char_count = len(re.sub(r"\s+", "", body))
    qa = _guess_qa_patterns(body)

    excerpt = body[:500] + ("…" if len(body) > 500 else "")
    if char_count < 120:
        host = urlparse(url).netloc
        excerpt = (
            f"[본문 추출이 짧습니다 — {host}. "
            "네이버 VIEW는 3단계 Playwright가 필요할 수 있습니다.] "
            + excerpt
        )

    return PostStructure(
        url=url,
        title=title,
        headings=headings,
        char_count=char_count,
        qa_patterns=qa,
        excerpt=excerpt,
    )
