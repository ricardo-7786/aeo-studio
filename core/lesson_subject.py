"""레슨 과목(기타·보컬 등) — STT·제목·타겟 키워드에서 감지."""

from __future__ import annotations

import re

from config.settings import AcademyProfile

# academy.services 항목명 → STT·제목에서 찾을 신호
_SUBJECT_SIGNALS: dict[str, re.Pattern[str]] = {
    "보컬": re.compile(
        r"보컬|vocal|발성|호흡|롱톤|아으에이오우|성대|고음|두성|딕션|비음|흉성|헤드보이스",
        re.I,
    ),
    "기타": re.compile(
        r"기타|guitar|어쿠스틱|일렉(?:트릭)?|코드|프렛|피킹|스트로킹|카포|운지|리프|솔로|펜타토닉",
        re.I,
    ),
    "피아노": re.compile(r"피아노|piano|건반|스케일|하농|체르니|아르페지오", re.I),
    "베이스": re.compile(r"베이스|bass|슬랩|그루브", re.I),
    "드럼": re.compile(r"드럼|drum|스네어|하이햇|킥|필인|루디먼트", re.I),
    "미디작곡": re.compile(r"미디|작곡|DAW|큐베이스|에이블톤|로직|프로툴스|MIDI", re.I),
    "랩": re.compile(r"랩|힙합|플로우|라임", re.I),
}


def _normalize_services(academy: AcademyProfile) -> list[str]:
    return [s.strip() for s in (academy.services or []) if str(s).strip()]


def detect_lesson_subject(
    academy: AcademyProfile,
    *,
    source_text: str = "",
    lesson_title: str = "",
    target_keyword: str = "",
) -> str:
    """이번 글의 대표 과목. academy.services 중 하나, 없으면 첫 과목."""
    services = _normalize_services(academy)
    if not services:
        return "레슨"

    scores: dict[str, int] = {s: 0 for s in services}
    kw = (target_keyword or "").replace(" ", "")
    title = lesson_title or ""
    body = source_text or ""
    body_blob = f"{title}\n{body}"

    body_scores: dict[str, int] = {s: 0 for s in services}
    kw_scores: dict[str, int] = {s: 0 for s in services}

    for svc in services:
        compact = svc.replace(" ", "")
        if svc in title or compact in title:
            body_scores[svc] += 8
        pattern = _SUBJECT_SIGNALS.get(svc)
        if pattern and pattern.search(body_blob):
            body_scores[svc] += 5 + len(pattern.findall(body_blob))
        if compact and compact in kw:
            kw_scores[svc] += 12
        if f"{compact}학원" in kw:
            kw_scores[svc] += 12

    best_body = max(body_scores.items(), key=lambda x: x[1])
    if best_body[1] >= 5:
        return best_body[0]

    best_kw = max(kw_scores.items(), key=lambda x: x[1])
    if best_kw[1] > 0:
        return best_kw[0]

    if best_body[1] > 0:
        return best_body[0]
    return services[0]


def _subject_in_keyword(keyword: str, subject: str) -> bool:
    compact = subject.replace(" ", "")
    kw = (keyword or "").replace(" ", "")
    if not compact or not kw:
        return False
    return compact in kw or f"{compact}학원" in kw


def resolve_template_keyword(plan, user_keyword: str = "") -> str:
    """SerpAPI·템플릿 검색 키워드 — STT/레슨 과목 우선, 폼 기본값(보컬) 덮어쓰기 방지."""
    from core.keyword_rotation import KeywordPlan

    if not isinstance(plan, KeywordPlan):
        return (user_keyword or "").strip() or getattr(plan, "title_keyword", "")

    detected = (plan.title_keyword or "").strip()
    user_kw = (user_keyword or "").strip()
    if not user_kw:
        return detected
    if _subject_in_keyword(user_kw, plan.lesson_subject):
        return user_kw
    return detected
