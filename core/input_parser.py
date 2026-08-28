"""입력 수집: 원본 텍스트 / 파일 / 네이버 블로그 URL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

NAVER_BLOG_HOSTS = {"blog.naver.com", "m.blog.naver.com"}
USER_AGENT = (
    "Mozilla/5.0 (compatible; AcademyAEOBot/1.0; +https://example-academy.com)"
)


@dataclass
class SourceContent:
    title: str
    body: str
    source_type: str  # text | file | naver_url | audio
    source_ref: str


def make_source(title: str, body: str, source_type: str, source_ref: str) -> SourceContent:
    return SourceContent(title=title, body=body, source_type=source_type, source_ref=source_ref)


def looks_like_url(value: str) -> bool:
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        return False
    parsed = urlparse(value)
    return bool(parsed.netloc)


def is_naver_blog_url(url: str) -> bool:
    host = urlparse(url).netloc.lower().replace("www.", "")
    return host in NAVER_BLOG_HOSTS


def _normalize_naver_url(url: str) -> str:
    """모바일 URL을 PC URL로 정규화하고 PostView 형태로 맞춘다."""
    url = url.strip()
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if host.startswith("m.blog.naver.com"):
        url = url.replace("m.blog.naver.com", "blog.naver.com", 1)
        parsed = urlparse(url)

    # /PostView.naver?blogId=x&logNo=y 형태는 그대로 사용
    if "PostView" in parsed.path or "PostView" in url:
        return url

    # blog.naver.com/{blogId}/{logNo}
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[1].isdigit():
        blog_id, log_no = parts[0], parts[1]
        return (
            "https://blog.naver.com/PostView.naver"
            f"?blogId={blog_id}&logNo={log_no}&redirect=Dlog"
        )
    return url


def fetch_naver_blog(url: str, timeout: int = 20) -> SourceContent:
    """네이버 블로그 본문을 스크래핑한다 (공개글 기준)."""
    if not is_naver_blog_url(url):
        raise ValueError("네이버 블로그 URL만 지원합니다: " + url)

    target = _normalize_naver_url(url)
    resp = requests.get(
        target,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")

    # iframe 본문 (구형 스킨)
    iframe = soup.select_one("iframe#mainFrame")
    if iframe and iframe.get("src"):
        iframe_src = iframe["src"]
        if iframe_src.startswith("/"):
            iframe_src = "https://blog.naver.com" + iframe_src
        frame_resp = requests.get(
            iframe_src,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        frame_resp.raise_for_status()
        frame_resp.encoding = frame_resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(frame_resp.text, "lxml")

    title_el = (
        soup.select_one(".se-title-text")
        or soup.select_one(".pcol1")
        or soup.select_one("title")
    )
    title = title_el.get_text(" ", strip=True) if title_el else "네이버 블로그 글"
    title = re.sub(r"\s*:\s*네이버 블로그\s*$", "", title).strip()

    body_parts: list[str] = []
    selectors = [
        ".se-main-container .se-text-paragraph",
        ".se-main-container",
        "#postViewArea",
        ".post-view",
        "#post-view",
    ]
    for sel in selectors:
        nodes = soup.select(sel)
        if not nodes:
            continue
        for node in nodes:
            text = node.get_text("\n", strip=True)
            if text:
                body_parts.append(text)
        if body_parts:
            break

    body = "\n\n".join(dict.fromkeys(body_parts)).strip()
    if not body:
        raise ValueError(
            "네이버 블로그 본문을 추출하지 못했습니다. "
            "공개글인지, URL이 올바른지 확인하세요."
        )

    return SourceContent(
        title=title,
        body=body,
        source_type="naver_url",
        source_ref=url,
    )


def load_text_file(path: str) -> SourceContent:
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("입력 파일이 비어 있습니다.")
    first_line = text.splitlines()[0].strip()
    title = first_line[:80] if first_line else p.stem
    return SourceContent(
        title=title,
        body=text,
        source_type="file",
        source_ref=str(p.resolve()),
    )


def load_raw_text(text: str, title: str | None = None) -> SourceContent:
    text = text.strip()
    if not text:
        raise ValueError("입력 텍스트가 비어 있습니다.")
    inferred = title or text.splitlines()[0].strip()[:80] or "레슨 기록"
    return SourceContent(
        title=inferred,
        body=text,
        source_type="text",
        source_ref="stdin/cli",
    )


def resolve_input(
    *,
    text: str | None = None,
    file_path: str | None = None,
    url: str | None = None,
) -> SourceContent:
    """CLI 인자를 우선순위에 따라 SourceContent로 변환."""
    if url:
        return fetch_naver_blog(url)
    if file_path:
        return load_text_file(file_path)
    if text:
        # 텍스트가 URL처럼 보이면 자동 분기
        if looks_like_url(text) and is_naver_blog_url(text):
            return fetch_naver_blog(text)
        return load_raw_text(text)
    raise ValueError("--text, --file, --url 중 하나를 지정하세요.")
