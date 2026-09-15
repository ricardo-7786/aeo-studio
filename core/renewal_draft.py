"""기존 블로그 글 리뉴얼용 초안 생성 — 복붙용 (자동 발행 아님)."""

from __future__ import annotations

from datetime import date
from typing import Any

from config.settings import AcademyProfile
from core.openai_json import chat_json


def fetch_existing_post(url: str) -> dict[str, Any]:
    """네이버/티스토리 URL → 제목·소제목·발췌."""
    from core.template.content_extractor import extract_post_structure

    post = extract_post_structure(url.strip())
    return {
        "url": post.url,
        "title": post.title,
        "headings": post.headings[:12],
        "char_count": post.char_count,
        "excerpt": (post.excerpt or "")[:2500],
        "ok": post.char_count >= 80 or bool(post.title),
    }


def generate_renewal_draft(
    *,
    keyword: str,
    academy: AcademyProfile,
    api_key: str,
    model: str = "gpt-4o-mini",
    group: str = "",
    related_keywords: list[str] | None = None,
    rank_note: str = "",
    lesson_memo: str = "",
    source_url: str = "",
    existing_post: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """네이버/티스토리 기존 글에 붙일 리뉴얼 블록 JSON."""
    related = related_keywords or []
    related = [k for k in related if k and k != keyword][:5]
    today = date.today()
    month_label = f"{today.year}년 {today.month}월"

    existing = existing_post
    fetch_error = ""
    if source_url.strip() and not existing:
        try:
            existing = fetch_existing_post(source_url)
            if not existing.get("ok"):
                fetch_error = (
                    f"본문 추출이 짧습니다({existing.get('char_count', 0)}자). "
                    "제목·소제목만 참고하거나, 메모를 더 적어 주세요."
                )
        except Exception as exc:  # noqa: BLE001
            fetch_error = f"글 불러오기 실패: {exc}"
            existing = None

    existing_block = "(기존 글 URL 없음 — 키워드·학원 정보만으로 작성. 톤은 담백한 학원 블로그)"
    if existing:
        heads = "\n".join(f"- {h}" for h in (existing.get("headings") or [])[:10])
        existing_block = f"""URL: {existing.get('url') or source_url}
기존 제목: {existing.get('title') or '(없음)'}
글자 수(추출): {existing.get('char_count', 0)}
소제목:
{heads or '- (없음)'}
본문 앞부분(톤·문장 리듬·이미 쓴 내용 파악용):
{existing.get('excerpt') or '(없음)'}"""

    system = """당신은 한국 로컬 학원 네이버 블로그 '리뉴얼' 카피라이터입니다.
역할: 기존 글 상단(도입 직후)에 붙여도 어색하지 않은 '짧은 업데이트 블록'만 만듭니다.

성공 기준:
- 기존 글의 말투·문장 길이·강조 방식(👉, 짧은 문단 등)을 닮을 것
- 앞에 붙였을 때 바로 아래 기존 문단으로 자연스럽게 이어질 것
- 기존에 이미 있는 내용은 반복하지 말 것

실패 예:
- 갑자기 다른 과목·학원 광고·CODA 홍보
- '이번 달 팁입니다'처럼 동떨어진 매거진 톤
- 기존 글과 같은 기초/맞춤수업 설명을 다시 씀

허구 금지. 응답은 JSON만."""

    user = f"""[학원]
- 이름: {academy.name}
- 위치: {academy.location}
- 주소: {academy.address}
- 전화: {academy.phone}
- 웹: {academy.url}
- 과목: {', '.join(academy.services)}
- 근거: {academy.evidence or '(없음)'}

[타깃 키워드] {keyword}
[키워드 그룹] {group or '(없음)'}
[관련 키워드] {', '.join(related) if related else '(없음)'}
[순위 메모] {rank_note or '(없음)'}
[최근 레슨/현장 메모 — 있으면 업데이트 핵심]
{lesson_memo.strip() or '(메모 없음)'}

[기존 글]
{existing_block}

작업:
A) already_covered: 기존 글이 이미 다루는 주제 3~8개
B) style_match: 기존 글 문체 특징 2~4개 (예: 짧은 문단, 👉 강조, 존댓말, 리스트)
C) paste_anchor: 어디에 붙일지 한 문장
   예: "첫 도입 문단(👉 …) 바로 아래, 다음 소제목 전에 삽입"
D) update_heading: "({month_label} 업데이트)" + 기존 소제목 톤과 맞는 짧은 제목
E) update_body: 2~3문단(또는 4~7문장). 규칙:
   - 첫 문장은 기존 도입과 이어지게 (갑작스러운 주제 점프 금지)
   - style_match를 반영 (👉를 쓰면 핵심 1줄에만, 남발 금지)
   - already_covered 반복 금지
   - 메모 있으면 그 구체 포인트 중심 / 없으면 기존에 없는 한 가지 실천 팁만
   - 다른 과목 나열 금지
   - 학원명·키워드 1회 이내
   - 기존 글에 이미 톡톡/문의 CTA가 있으면 update_body 끝 CTA 생략
   - 마크다운·#, * 금지. 줄바꿈은 \\n\\n
F) bridge_note: 붙인 뒤 바로 아래 기존 문단과 어떻게 이어지는지 한 줄 (사용자 참고용)

JSON:
{{
  "already_covered": ["..."],
  "style_match": ["..."],
  "paste_anchor": "삽입 위치 한 문장",
  "bridge_note": "아래 본문과의 연결 설명 한 줄",
  "title_suggestions": ["기존 제목 기반 수정안 3개"],
  "update_heading": "({month_label} 업데이트) …",
  "update_body": "본문만",
  "photo_checklist": ["0~3개"],
  "hashtags": ["#태그"],
  "howto": "3~5단계. paste_anchor를 포함할 것"
}}

학원 공식 명칭은 '{academy.name}'.
"""

    parsed = chat_json(
        api_key=api_key,
        model=model,
        system=system,
        user=user,
        temperature=0.35,
    )

    titles = parsed.get("title_suggestions") or []
    if not isinstance(titles, list):
        titles = []
    titles = [str(t).strip() for t in titles if str(t).strip()][:5]

    photos = parsed.get("photo_checklist") or []
    if not isinstance(photos, list):
        photos = []
    photos = [str(p).strip() for p in photos if str(p).strip()][:6]

    tags = parsed.get("hashtags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()][:8]

    covered = parsed.get("already_covered") or []
    if not isinstance(covered, list):
        covered = []
    covered = [str(c).strip() for c in covered if str(c).strip()][:10]

    style_match = parsed.get("style_match") or []
    if not isinstance(style_match, list):
        style_match = []
    style_match = [str(s).strip() for s in style_match if str(s).strip()][:6]

    paste_anchor = str(parsed.get("paste_anchor") or "").strip()
    bridge_note = str(parsed.get("bridge_note") or "").strip()
    if not paste_anchor:
        paste_anchor = "첫 도입 문단 바로 아래, 다음 소제목 전에 삽입"

    body = str(parsed.get("update_body") or "").strip()
    heading = str(parsed.get("update_heading") or f"({month_label} 업데이트)").strip()
    howto = str(parsed.get("howto") or "").strip()
    if source_url.strip() and "http" not in howto:
        howto = (
            f"1) 아래 URL 글을 연다: {source_url.strip()}\n"
            f"2) 수정\n"
            f"3) 위치: {paste_anchor}\n"
            "4) 소제목 줄은 굵게(또는 소제목 스타일)로 지정\n"
            "5) 제목 수정안 중 하나 적용 후 발행\n"
            + howto
        )

    paste_block = f"{heading}\n\n{body}".strip()

    return {
        "keyword": keyword,
        "group": group,
        "related_keywords": related,
        "already_covered": covered,
        "style_match": style_match,
        "paste_anchor": paste_anchor,
        "bridge_note": bridge_note,
        "title_suggestions": titles,
        "update_heading": heading,
        "update_body": body,
        "photo_checklist": photos,
        "hashtags": tags,
        "howto": howto,
        "paste_block": paste_block,
        "month_label": month_label,
        "source_url": source_url.strip(),
        "existing_title": (existing or {}).get("title") or "",
        "existing_char_count": (existing or {}).get("char_count") or 0,
        "fetch_error": fetch_error,
        "fetch_ok": bool(existing and existing.get("ok")),
        "memo_used": bool(lesson_memo.strip()),
    }


def related_keywords_for(
    keyword: str, group: str, all_keywords: list[str], groups: dict[str, str]
) -> list[str]:
    if not group:
        return []
    return [k for k in all_keywords if groups.get(k) == group and k != keyword]
