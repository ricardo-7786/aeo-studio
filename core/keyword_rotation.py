"""인접 지역 키워드 로테이션 + STT 문제 키워드 결합."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from config.industry import INDUSTRY_META, normalize_industry
from config.settings import AcademyProfile

# (정규식, 제목용 짧은 키워드)
PROBLEM_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"고음.{0,8}(씹|뭉개|막히|안 나|안나)"), "고음 씹힘"),
    (re.compile(r"(숨.{0,4}차|호흡.{0,6}(부족|짧|무너)|숨이 짧)"), "호흡 부족"),
    (re.compile(r"(갈라|갈라지|쉰 목|목이 잠)"), "고음 갈라짐"),
    (re.compile(r"(비음|코로 빠|콧소리)"), "비음"),
    (re.compile(r"(음정.{0,6}(흔들|불안|안 맞)|피치.{0,4}(흔들|불안))"), "음정 불안"),
    (re.compile(r"(발음.{0,8}(씹|뭉개|안 들)|딕션)"), "발음 뭉개짐"),
    (re.compile(r"(성량|볼륨).{0,6}(작|부족|안 나)"), "성량 부족"),
    (re.compile(r"(두성|헤드보이스).{0,8}(전환| bridging|브릿지|막히)"), "두성 전환"),
    (re.compile(r"(저음.{0,6}(안 나|빈약)|흉성.{0,4}부족)"), "저음 빈약"),
    (re.compile(r"(리듬.{0,6}(밀리|당겨|불안)|박자.{0,4}(안 맞))"), "리듬 불안"),
    (re.compile(r"(성대.{0,6}접촉|클로저|기식음)"), "성대 접촉"),
]

DEFAULT_ADJACENT = ("화정", "행신", "원당", "삼송")


def parse_area_list(raw: str | list[str] | None) -> list[str]:
    if isinstance(raw, list):
        parts = raw
    else:
        parts = re.split(r"[,/\n]+", raw or "")
    out: list[str] = []
    for p in parts:
        t = re.sub(r"\s+", " ", str(p).strip())
        t = t.replace("역", "") if t.endswith("역") and len(t) > 1 else t
        if t and t not in out:
            out.append(t)
    return out


def infer_home_area(academy: AcademyProfile) -> str:
    blob = f"{academy.location} {academy.address}"
    station = re.search(r"([가-힣A-Za-z0-9]+)역", blob)
    if station:
        return station.group(1)
    district = re.search(r"([가-힣]+)구", blob)
    if district:
        return district.group(1).replace("구", "")
    return ""


def adjacent_areas_for(academy: AcademyProfile) -> list[str]:
    configured = parse_area_list(getattr(academy, "adjacent_areas", None) or [])
    home = infer_home_area(academy)
    ordered: list[str] = []
    if home:
        ordered.append(home)
    for a in configured:
        if a not in ordered:
            ordered.append(a)
    if not ordered:
        ordered = list(DEFAULT_ADJACENT)
    elif home == "화정" and not configured:
        for a in DEFAULT_ADJACENT:
            if a not in ordered:
                ordered.append(a)
    return ordered


def extract_problem_keywords(source_text: str, *, limit: int = 3) -> list[str]:
    text = source_text or ""
    found: list[str] = []
    for pattern, label in PROBLEM_PATTERNS:
        if pattern.search(text) and label not in found:
            found.append(label)
        if len(found) >= limit:
            break
    return found


def _rotation_seed(*, business_key: str = "") -> int:
    seed = date.today().toordinal()
    if not business_key:
        return seed
    try:
        from db.connection import is_db_configured
        from db.draft_repo import count_drafts

        if is_db_configured():
            seed += count_drafts(business_key)
    except Exception:  # noqa: BLE001
        pass
    return seed


@dataclass(frozen=True)
class KeywordPlan:
    home_area: str
    focus_area: str
    rotation_index: int
    areas: list[str]
    problem_keywords: list[str]
    title_keyword: str
    secondary_keywords: list[str]
    title_hint: str

    def prompt_block(self) -> str:
        problems = ", ".join(self.problem_keywords) if self.problem_keywords else "(원문에 구체 고민이 있으면 그 표현을 사용)"
        secondary = ", ".join(self.secondary_keywords) if self.secondary_keywords else "(없음)"
        return f"""[키워드 로테이션 — 이번 발행]
- 학원 본점 지역(본문에 1회 이상, 제목 남용 금지): {self.home_area or '(미지정)'}
- 이번 글 제목·리드 지역 키워드(필수): {self.focus_area}
- 제목 핵심 키워드: {self.title_keyword}
- STT에서 감지된 문제 키워드: {problems}
- 보조 지역(본문에 과다 반복 금지, 필요 시 1회): {secondary}
- 권장 제목 골격: {self.title_hint}
규칙:
1. 제목은 [이번 지역] + [STT 문제 또는 실제 곡/고민] + [레슨·해결 톤]. 키워드만 나열 금지.
2. 본문 전체를 다른 지역 글로 위장하지 말 것. 실제 위치({self.home_area})는 사실대로 1회 이상.
3. 인접 지역은 '다니는 길·통학권·근처 수강생' 맥락으로만 자연스럽게.
4. 원문에 없는 문제를 지어내지 말 것. 문제 키워드가 없으면 원문 고민을 쓴다."""


def build_keyword_plan(
    academy: AcademyProfile,
    source_text: str,
    *,
    rotation_index: int | None = None,
    focus_area_override: str | None = None,
) -> KeywordPlan:
    areas = adjacent_areas_for(academy)
    home = infer_home_area(academy) or (areas[0] if areas else "")
    n = max(len(areas), 1)
    idx = rotation_index
    if idx is None:
        idx = _rotation_seed(business_key=academy.business_key) % n
    else:
        idx = idx % n

    override = (focus_area_override or "").strip()
    if override:
        focus = override.replace("역", "") if override.endswith("역") else override
        if focus in areas:
            idx = areas.index(focus)
        else:
            areas = [focus] + [a for a in areas if a != focus]
            idx = 0
    focus = areas[idx]
    problems = extract_problem_keywords(source_text)
    industry = normalize_industry(getattr(academy, "industry", "general"))
    meta = INDUSTRY_META[industry]
    primary = (academy.services[0] if academy.services else meta["entity"]).strip() or meta["entity"]
    suffix = {
        "education": "학원",
        "restaurant": "맛집",
        "clinic": "클리닉",
        "fitness": "센터",
        "beauty": "샵",
        "general": "",
    }.get(industry, "")

    problem_bit = problems[0] if problems else ""
    title_keyword = f"{focus} {primary}{suffix}".strip()
    if problem_bit:
        title_hint = f"{focus} {primary} {problem_bit} 레슨 일지"
    else:
        title_hint = f"{title_keyword} 레슨 일지"

    secondary = [a for a in areas if a != focus][:3]
    return KeywordPlan(
        home_area=home,
        focus_area=focus,
        rotation_index=idx,
        areas=areas,
        problem_keywords=problems,
        title_keyword=title_keyword,
        secondary_keywords=secondary,
        title_hint=title_hint,
    )
