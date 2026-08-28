"""템플릿 JSON → LLM 프롬프트 블록."""

from __future__ import annotations

from core.template.models import AeoTemplate


def format_template_guide(template: AeoTemplate | dict) -> str:
    t = template if isinstance(template, AeoTemplate) else AeoTemplate.model_validate(template)
    sections = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(t.section_structure))
    qa = "\n".join(f"  - {q}" for q in t.qa_pairs)
    urls = "\n".join(f"  - {u}" for u in t.source_urls)
    return f"""[상위 노출 참고 구조 — 문장·표현 복사 금지, 목차·흐름만 따를 것]
- 키워드: {t.target_keyword} ({t.channel})
- 참고 URL:
{urls or '  - (없음)'}
- 제목 패턴: {t.recommended_title_pattern}
- 권장 글자 수(공백 제외): 약 {t.target_word_count}자
- 소제목 흐름:
{sections or '  (자유)'}
- FAQ에 넣을 질문 패턴(원문 STT 내용으로 답할 것):
{qa or '  (자유)'}
- {t.notes or '상위 글의 문장을 베끼지 말고, 위 구조 안에 현장 STT/메모 사실만 채워 넣으세요.'}"""
