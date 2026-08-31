"""블로그 URL → 제목·소제목·글자 수·Q&A 패턴 추출.

1순위: 네이버 PC URL → m.blog.naver.com 변환 후 HTML 파싱
폴백: 본문 120자 미만이면 Jina Reader (r.jina.ai)
"""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from core.template.models import PostStructure

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

QUESTION_RE = re.compile(r"(^.+\?\s*$|^Q[\.\:].+|^질문[\:\.]?\s*.+)", re.M | re.I)
MIN_BODY_CHARS = 120
JINA_READER_BASE = "https://r.jina.ai/"

# 네이버 UI·표 셀 등 소제목으로 쓰이지 않는 짧은 텍스트
HEADING_NOISE_EXACT = frozenset(
    {
        "블로그",
        "카테고리",
        "공유하기",
        "댓글",
        "댓글쓰기",
        "이전글",
        "다음글",
        "목록",
        "기간",
        "가격",
        "혜택",
        "구성",
        "비고",
    }
)
HEADING_NOISE_PREFIXES = (
    "카테고리 이동",
    "이 블로그의",
    "이 장소의",
    "URL Source:",
)

NAVER_HEADING_SELECTORS = (
    ".se-section-title",
    ".se-module.se-quote .se-text-paragraph",
    ".se-module-text.se-quote .se-text-paragraph",
    ".se-quote .se-text-paragraph",
)

CONTENT_ROOT_SELECTORS = (
    "div.se-main-container",
    "div#postViewArea",
    "div.post-view",
    "div.se-viewer",
    "article",
    "main",
    "div.entry-content",
    "div.tt_article_useless_p_margin",
)


def _env_bool(key: str, default: bool = True) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def to_naver_mobile_url(url: str) -> str:
    """blog.naver.com PC URL → m.blog.naver.com (iframe 회피)."""
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower().replace("www.", "")

    if host == "m.blog.naver.com":
        return url.strip()

    if host != "blog.naver.com":
        return url.strip()

    path_match = re.match(r"^/([^/]+)/(\d+)/?", parsed.path or "")
    if path_match:
        blog_id, log_no = path_match.group(1), path_match.group(2)
        if blog_id.lower() not in {"postview.naver", "postlist.naver"}:
            return f"https://m.blog.naver.com/{blog_id}/{log_no}"

    qs = parse_qs(parsed.query)
    blog_id = (qs.get("blogId") or qs.get("blogid") or [None])[0]
    log_no = (qs.get("logNo") or qs.get("logno") or [None])[0]
    if blog_id and log_no:
        return f"https://m.blog.naver.com/{blog_id}/{log_no}"

    return url.strip()


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _content_root(soup: BeautifulSoup):
    for sel in CONTENT_ROOT_SELECTORS:
        node = soup.select_one(sel)
        if node:
            return node
    return soup.body or soup


def _is_noise_heading(text: str) -> bool:
    t = _clean_text(text)
    if len(t) < 4 or len(t) > 100:
        return True
    if t in HEADING_NOISE_EXACT:
        return True
    if any(t.startswith(prefix) for prefix in HEADING_NOISE_PREFIXES):
        return True
    if re.fullmatch(r"[\d,./원%+~\-\s]+", t):
        return True
    return False


def _append_heading(headings: list[str], text: str, *, skip_if: str = "") -> None:
    t = _clean_text(text)
    if _is_noise_heading(t):
        return
    if skip_if and t == _clean_text(skip_if):
        return
    if t not in headings:
        headings.append(t)


def _extract_headings_from_soup(soup: BeautifulSoup, *, page_title: str = "") -> list[str]:
    """본문 컨테이너 안의 네이버 SE 소제목만 추출 (UI h1/h2 제외)."""
    root = _content_root(soup)
    headings: list[str] = []
    title_skip = page_title

    for sel in NAVER_HEADING_SELECTORS:
        for tag in root.select(sel):
            _append_heading(headings, tag.get_text(" ", strip=True), skip_if=title_skip)

    for section in root.select(".se-section"):
        classes = section.get("class") or []
        if "se-section-documentTitle" in classes:
            continue
        for tag in section.select(".se-title-text"):
            _append_heading(headings, tag.get_text(" ", strip=True), skip_if=title_skip)

    for tag in root.find_all(["h2", "h3", "h4"]):
        _append_heading(headings, tag.get_text(" ", strip=True), skip_if=title_skip)

    return headings[:20]


def _extract_headings_from_markdown(md: str) -> list[str]:
    headings: list[str] = []
    for line in (md or "").splitlines():
        m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if m:
            t = m.group(1).strip()
            if t and t not in headings:
                headings.append(t)
    return headings[:20]


def _extract_body_from_soup(soup: BeautifulSoup) -> str:
    root = _content_root(soup)
    return root.get_text("\n", strip=True)


def _guess_qa_patterns(text: str) -> list[str]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    out: list[str] = []
    for line in lines:
        if QUESTION_RE.match(line) and line not in out:
            out.append(line[:120])
        if len(out) >= 8:
            break
    return out


def _parse_jina_response(raw: str) -> tuple[str, str]:
    """Jina Reader 응답 → (title, markdown body)."""
    text = (raw or "").strip()
    title = ""
    body = text

    if text.startswith("Title:"):
        lines = text.splitlines()
        title = lines[0].replace("Title:", "", 1).strip()
        body = "\n".join(lines[1:]).strip()

    marker = "Markdown Content:"
    if marker in body:
        _, _, body = body.partition(marker)
        body = body.strip()

    # Jina 메타 헤더 제거
    skip_prefixes = ("URL Source:", "Published Time:", "Warning:")
    cleaned: list[str] = []
    for line in body.splitlines():
        if any(line.strip().startswith(p) for p in skip_prefixes):
            continue
        cleaned.append(line)
    body = "\n".join(cleaned).strip()
    return title, body


def _build_post_structure(
    *,
    original_url: str,
    fetch_url: str,
    title: str,
    body: str,
    headings: list[str],
    source: str,
) -> PostStructure:
    char_count = _char_count(body)
    qa = _guess_qa_patterns(body)
    excerpt = body[:500] + ("…" if len(body) > 500 else "")
    if char_count < MIN_BODY_CHARS:
        excerpt = (
            f"[본문 추출 {char_count}자 — {source}. "
            f"fetch={fetch_url}] "
            + excerpt
        )
    return PostStructure(
        url=original_url,
        title=title,
        headings=headings,
        char_count=char_count,
        qa_patterns=qa,
        excerpt=excerpt,
    )


def _fetch_html(url: str, *, timeout: int) -> BeautifulSoup:
    res = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": MOBILE_USER_AGENT,
            "Accept-Language": "ko-KR,ko;q=0.9",
        },
    )
    res.raise_for_status()
    res.encoding = res.encoding or "utf-8"
    return BeautifulSoup(res.text, "lxml")


def _extract_from_html(
    fetch_url: str,
    *,
    original_url: str,
    timeout: int,
) -> PostStructure:
    soup = _fetch_html(fetch_url, timeout=timeout)

    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = _clean_text(og["content"])
    if not title and soup.title:
        title = _clean_text(soup.title.get_text())

    body = _extract_body_from_soup(soup)
    headings = _extract_headings_from_soup(soup, page_title=title)

    return _build_post_structure(
        original_url=original_url,
        fetch_url=fetch_url,
        title=title,
        body=body,
        headings=headings,
        source="mobile HTML",
    )


def _extract_from_jina(
    fetch_url: str,
    *,
    original_url: str,
    timeout: int,
) -> PostStructure | None:
    if not _env_bool("JINA_READER_ENABLED", True):
        return None

    jina_url = f"{JINA_READER_BASE}{fetch_url}"
    headers = {
        "Accept": "text/plain",
        "User-Agent": USER_AGENT,
    }
    api_key = (os.getenv("JINA_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        res = requests.get(jina_url, timeout=max(timeout, 30), headers=headers)
        res.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ! Jina Reader skip ({fetch_url}): {exc}")
        return None

    title, body = _parse_jina_response(res.text)
    headings = _extract_headings_from_markdown(body)

    return _build_post_structure(
        original_url=original_url,
        fetch_url=fetch_url,
        title=title,
        body=body,
        headings=headings,
        source="Jina Reader",
    )


def extract_post_structure(url: str, *, timeout: int = 20) -> PostStructure:
    original = url.strip()
    fetch_url = to_naver_mobile_url(original)

    try:
        html_result = _extract_from_html(
            fetch_url,
            original_url=original,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        print(f"  ! HTML fetch skip ({fetch_url}): {exc}")
        html_result = _build_post_structure(
            original_url=original,
            fetch_url=fetch_url,
            title="",
            body="",
            headings=[],
            source="mobile HTML (failed)",
        )

    if html_result.char_count >= MIN_BODY_CHARS:
        return html_result

    jina_result = _extract_from_jina(
        fetch_url,
        original_url=original,
        timeout=timeout,
    )
    if jina_result and jina_result.char_count >= MIN_BODY_CHARS:
        return jina_result
    if jina_result and jina_result.char_count > html_result.char_count:
        return jina_result

    return html_result
