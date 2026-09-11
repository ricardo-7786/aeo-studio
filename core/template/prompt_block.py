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
    section_count = len(t.section_structure)
    qa = "\n".join(f"  - {q}" for q in t.qa_pairs)
    urls = "\n".join(f"  - {u}" for u in t.source_urls)
    notes = t.notes or (
        "참고 글 소제목·문장을 복사하지 말고, STT 포인트명으로 ## 소제목을 새로 작성하세요."
    )
    section_hint = (
        f"참고 글 본문은 약 {section_count}개 구간 분량 — 구간 **수·글자 수**만 참고. "
        f"## 소제목은 원문 STT 연습명·기술명으로만 작성(참고 글 소제목 문구 복사 금지)."
        if section_count
        else "구간 수는 STT 포인트 수에 맞게 3~5개. ## 소제목은 연습명·기술명만."
    )
    return f"""[상위 노출 참고 구조 — 문장·소제목·스토리 복사 금지, 분량·FAQ 패턴만 참고]
- 키워드: {t.target_keyword} ({t.channel})
- 참고 URL (취미후기·성공 스토리일 수 있음 — STT 단일 레슨이면 그 서사를 따라 쓰지 말 것):
{urls or '  - (없음)'}
- 제목 패턴(키워드 조합만 참고): {t.recommended_title_pattern}
- 권장 글자 수(공백 제외): 약 {t.target_word_count}자
- 본문 구간: {section_hint}
- FAQ 질문 패턴(원문·프로필로 답 가능한 것만 — 일반론·허구 답 금지):
{qa or '  (자유)'}
- {notes}

[템플릿 적용 규칙 — 필수]
1. 참고 URL 글의 소제목·스토리 흐름(퇴근 후 도전, N개월 여정 등)을 본문에 재현하지 말 것.
2. ## 소제목 = STT·메모의 실제 연습 포인트·기술명·곡명. 예) ## 아으에이오우 롱톤으로 발음 길게 잡기
3. '서론', '문제 제기', '결심', '마무리' 등 단계명·메타 라벨을 ## Heading으로 출력 금지.
4. 원문에 없는 사건·기간·인물관계를 분량 채우기용으로 추가 금지 — [학원 고정 사실]·연락처·통학 맥락으로만 보완."""
