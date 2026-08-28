"""업종별 프롬프트 컨텍스트 — 범용 AEO 앱."""

from __future__ import annotations

INDUSTRIES = ("education", "restaurant", "clinic", "fitness", "beauty", "general")

INDUSTRY_META: dict[str, dict[str, str]] = {
    "education": {
        "label": "교육·학원",
        "entity": "학원",
        "customer": "수강생·학부모",
        "schema_hint": "EducationalOrganization",
        "tone": "레슨·상담 현장 말투",
    },
    "restaurant": {
        "label": "음식점·카페",
        "entity": "매장",
        "customer": "손님",
        "schema_hint": "Restaurant",
        "tone": "점주·직원이 손님에게 설명하듯",
    },
    "clinic": {
        "label": "병원·클리닉",
        "entity": "클리닉",
        "customer": "환자",
        "schema_hint": "MedicalClinic",
        "tone": "의료 광고 규정을 지키며 사실만",
    },
    "fitness": {
        "label": "피트니스·운동",
        "entity": "센터",
        "customer": "회원",
        "schema_hint": "SportsActivityLocation",
        "tone": "트레이너 현장 코칭 말투",
    },
    "beauty": {
        "label": "미용·뷰티",
        "entity": "샵",
        "customer": "고객",
        "schema_hint": "BeautySalon",
        "tone": "시술·상담 현장 말투",
    },
    "general": {
        "label": "로컬 비즈니스",
        "entity": "업체",
        "customer": "고객",
        "schema_hint": "LocalBusiness",
        "tone": "현장에서 쓰는 말투",
    },
}


def normalize_industry(raw: str | None) -> str:
    key = (raw or "general").strip().lower()
    return key if key in INDUSTRY_META else "general"


def industry_context_block(industry: str) -> str:
    meta = INDUSTRY_META[normalize_industry(industry)]
    return f"""[업종 컨텍스트]
- 업종: {meta['label']} ({normalize_industry(industry)})
- 주체: {meta['entity']}
- 독자: {meta['customer']}
- Schema.org 보조 타입: {meta['schema_hint']}
- 말투: {meta['tone']}
- {meta['entity']} 고유명사·위치·수치는 그대로 유지하고, 업종에 맞지 않는 표현(예: 교육 업종이 아닌데 '레슨·입시')은 쓰지 않는다."""
