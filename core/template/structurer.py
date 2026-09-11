"""추출 데이터 → AEO 템플릿 JSON (LLM)."""

from __future__ import annotations

import json

from core.openai_json import chat_json
from core.template.models import AeoTemplate, PostStructure

SYSTEM = """당신은 SEO/AEO 콘텐츠 구조 분석가입니다.
여러 상위 노출 블로그 글의 '구조'만 분석해 JSON 템플릿을 만듭니다.
원문 문장을 복사·재작성하지 말고, 제목 패턴·소제목 흐름·글자 수·FAQ 질문 패턴만 추출하세요.

section_structure 작성 규칙(중요):
- 각 항목은 '구간 역할' 또는 '연습 포인트 슬롯'만 (예: "오늘 레슨 주제", "핵심 연습 1", "코칭·관찰", "다음 과제").
- '퇴근 후', '3개월', '새로운 도전', '만난 사람' 등 허구 스토리·후기형 문장 금지.
- 좋은 예: "오늘 연습: 모음 롱톤", "복식호흡 코칭", "발음·호흡 정리"
- 나쁜 예: "퇴근 후 쳇바퀴 일상, 노래로 찾아온 변화", "3개월 동안의 여정"

응답은 JSON 객체 하나만 출력합니다."""

FIELDS = """
필수 JSON 필드:
- recommended_title_pattern: 상위 글 제목의 키워드 조합 규칙 (예: "[지역키워드] + [고민/곡명] + [해결·후기]")
- section_structure: 문자열 배열 4~8개. 각 항목은 구간 역할·연습 슬롯(위 규칙). 스토리·후기형 문장 금지.
- target_word_count: 정수, 본문 평균 권장 글자 수(공백 제외). 상위 글 char_count 참고.
- qa_pairs: 문자열 배열, FAQ에 넣을 질문 패턴 3~5개
- notes: 하위 LLM에게 "참고 글 소제목 복사 금지, STT 포인트명으로 ## 작성" 한 줄 포함
"""


def structure_template(
    *,
    keyword: str,
    channel: str,
    posts: list[PostStructure],
    api_key: str,
    model: str = "gpt-4o-mini",
) -> AeoTemplate:
    if not posts:
        raise ValueError("분석할 포스팅 구조가 없습니다.")

    payload = []
    for p in posts:
        payload.append(
            {
                "url": p.url,
                "title": p.title,
                "headings": p.headings,
                "char_count": p.char_count,
                "qa_patterns": p.qa_patterns,
                "excerpt_hint": p.excerpt[:300],
            }
        )

    user = f"""키워드: {keyword}
채널: {channel}

[상위 글 구조 메타 — 문장 복사 금지]
{json.dumps(payload, ensure_ascii=False, indent=2)}

위 데이터를 종합해 하위 STT/레슨 메모를 채울 '골격' JSON을 만드세요.
section_structure에는 참고 글 headings 스타일(구체적·공감형)을 반영하되, 메타 단계명은 쓰지 마세요.
{FIELDS}"""

    parsed = chat_json(
        api_key=api_key,
        model=model,
        system=SYSTEM,
        user=user,
        temperature=0.3,
    )

    raw_count = parsed.get("target_word_count") or 700
    try:
        word_count = int(raw_count)
    except (TypeError, ValueError):
        word_count = 700

    default_notes = (
        "참고 글 소제목·스토리 문구를 ##에 복사하지 말고, STT 연습명·기술명으로 ## 소제목을 작성하세요."
    )
    notes = str(parsed.get("notes") or "").strip() or default_notes

    return AeoTemplate(
        target_keyword=keyword.strip(),
        channel=channel,
        recommended_title_pattern=str(parsed.get("recommended_title_pattern") or "").strip(),
        section_structure=[
            str(x).strip() for x in (parsed.get("section_structure") or []) if str(x).strip()
        ],
        target_word_count=word_count,
        qa_pairs=[str(x).strip() for x in (parsed.get("qa_pairs") or []) if str(x).strip()],
        source_urls=[p.url for p in posts],
        notes=notes,
    )
