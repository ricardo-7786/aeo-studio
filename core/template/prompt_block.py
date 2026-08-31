"""템플릿 JSON → LLM 프롬프트 블록."""

from __future__ import annotations

import re

from core.template.models import AeoTemplate


def parse_target_word_count(template_guide: str | None) -> int | None:
    """format_template_guide 출력에서 권장 글자 수 추출."""
    if not template_guide:
        return None
    m = re.search(r"권장 글자 수\(공백 제외\): 약 (\d+)자", template_guide)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def resolve_naver_target_chars(template_guide: str | None) -> int:
    """템플릿 연동 시 1,500~2,000자 목표. 없으면 기본 700."""
    raw = parse_target_word_count(template_guide)
    if raw is None:
        return 700
    return max(1500, min(2000, raw))


def format_template_guide(template: AeoTemplate | dict) -> str:
    t = template if isinstance(template, AeoTemplate) else AeoTemplate.model_validate(template)
    sections = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(t.section_structure))
    qa = "\n".join(f"  - {q}" for q in t.qa_pairs)
    urls = "\n".join(f"  - {u}" for u in t.source_urls)
    notes = t.notes or (
        "section_structure 항목을 ## 소제목으로 그대로 출력하지 말고, "
        "STT·메모 사실에 맞게 스토리형 소제목으로 변환하세요."
    )
    return f"""[상위 노출 참고 구조 — 문장·표현 복사 금지, 목차·흐름만 따를 것]
- 키워드: {t.target_keyword} ({t.channel})
- 참고 URL:
{urls or '  - (없음)'}
- 제목 패턴: {t.recommended_title_pattern}
- 권장 글자 수(공백 제외): 약 {t.target_word_count}자
- 소제목 흐름(스토리형 후보 — 아래를 ## 그대로 쓰지 말 것):
{sections or '  (자유)'}
- FAQ에 넣을 질문 패턴(원문 STT 내용으로 답할 것):
{qa or '  (자유)'}
- {notes}

[소제목 변환 규칙 — 필수]
1. '서론', '문제 제기', '결심', '마무리', '학원 소개' 등 단계명·메타 라벨을 ## Heading으로 출력 금지.
2. 위 '소제목 흐름'은 글의 전개 순서만 참고하고, 실제 ## 소제목은 STT·메모 사실 기반 스토리형 문장으로 새로 작성.
   예) ## 퇴근 후 쳇바퀴 일상, 노래로 찾아온 변화 / ## 1개월 차: 쌩목이 아닌 과학적 호흡 재설계
3. 상위 글 문장·표현 복사 금지. 구조(흐름·분량·FAQ 패턴)만 따를 것."""
