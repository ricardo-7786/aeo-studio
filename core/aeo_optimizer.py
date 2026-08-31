"""OpenAI 기반 AEO(Answer Engine Optimization) Markdown 변환."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from config.settings import AcademyProfile
from config.industry import INDUSTRY_META, industry_context_block, normalize_industry
from core.input_parser import SourceContent
from core.keyword_rotation import KeywordPlan
from core.openai_json import chat_json
from core.prompts import (
    get_aeo_system_prompt,
    keyword_density_block,
    positive_style_block,
    strict_negative_block,
)


class FAQItem(BaseModel):
    question: str = Field(description="검색·AI가 그대로 인용할 수 있는 질문")
    answer: str = Field(description="사실·수치·위치 기반의 짧은 답변")


class AEOArticle(BaseModel):
    """Structured Output 스키마 — AI 답변 엔진이 파싱하기 쉬운 단위."""

    title: str = Field(description="검색·AI 요약용 결론 중심 제목 (학원명 포함)")
    one_sentence_answer: str = Field(
        description="이 글의 핵심 주제를 1문장으로 답하는 결론"
    )
    markdown_body: str = Field(
        description="AEO Markdown 본문. 소제목은 ##(H2)만. # H1·FAQ·이미지 문법 금지"
    )
    faq: list[FAQItem] = Field(
        default_factory=list,
        description="FAQ 3~5개",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="고유명사·서비스명 키워드 (표기 일관 유지)",
    )
    meta_description: str = Field(
        description="120~155자 메타 설명 (학원명·위치·핵심 수치 포함)"
    )


def academy_context_block(academy: AcademyProfile) -> str:
    """업체 프로필 블록 (하위 호환 이름 유지)."""
    industry = normalize_industry(getattr(academy, "industry", "education"))
    meta = INDUSTRY_META[industry]
    services = ", ".join(academy.services)
    key = getattr(academy, "business_key", academy.name)
    return f"""{industry_context_block(industry)}

[{meta['entity']} 프로필 — 명칭 변경 금지]
- 업체 키: {key}
- 이름: {academy.name}
- 위치: {academy.location}
- 주소: {academy.address}
- 전화: {academy.phone}
- 웹사이트: {academy.url}
- 주요 서비스: {services}
- 근거/수치 문구: {academy.evidence}
"""


def _academy_context(academy: AcademyProfile) -> str:
    return academy_context_block(academy)


def _build_user_prompt(source: SourceContent, academy: AcademyProfile) -> str:
    return f"""{_academy_context(academy)}

[원본 메타]
- 소스 유형: {source.source_type}
- 원본 제목: {source.title}
- 참조: {source.source_ref}

[원본 본문]
{source.body}

위 원본을 AEO 최적화 블로그 포스트 JSON으로 변환하세요.
title에는 '{academy.name}'과 위치 키워드를 자연스럽게 포함하세요.
중요 포인트 녹음 STT가 여러 개면 하나의 레슨 일지로 모두 녹여 쓰고, 포인트별 구체적 내용이 빠지지 않게 하세요.
"""


def _normalize_markdown_body(body: str) -> str:
    """LLM이 # H1·이미지 placeholder·FAQ를 markdown_body에 넣은 경우 보정."""
    cleaned: list[str] = []
    for line in (body or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("## 자주 묻는 질문"):
            break
        if "image_url_placeholder" in line:
            continue
        if re.search(r"!\[[^\]]*\]\([^)]*\)", line):
            if "placeholder" in line.lower() or "image_url" in line.lower():
                continue
        h3 = re.match(r"^(\s*)#{3,}\s+(.*)$", line)
        if h3:
            line = f"{h3.group(1)}## {h3.group(2)}"
        else:
            h1 = re.match(r"^(\s*)#\s+(.*)$", line)
            if h1 and not line.lstrip().startswith("##"):
                line = f"{h1.group(1)}## {h1.group(2)}"
        cleaned.append(line.rstrip())
    return "\n".join(cleaned).strip()


def _build_source_text_prompt(
    source_text: str,
    academy: AcademyProfile,
    *,
    template_guide: str | None = None,
    keyword_plan: KeywordPlan | None = None,
) -> str:
    guide_block = f"\n\n{template_guide}\n" if template_guide else ""
    primary_keyword = keyword_plan.title_keyword if keyword_plan else academy.name
    title_hint = keyword_plan.title_hint if keyword_plan else f"{primary_keyword} 레슨 일지"
    evidence_block = ""
    if academy.evidence.strip():
        evidence_block = f"""
[학원 고정 사실 — markdown_body에 STT와 자연스럽게 1~2문장 연결 가능. 지어내기 금지]
- {academy.evidence}"""
    return f"""{_academy_context(academy)}
{guide_block}
{evidence_block}
{keyword_density_block(primary_keyword, field="markdown_body")}
{strict_negative_block()}
{positive_style_block()}

[원본 — 레슨 기록 (익명화됨)]
{source_text}

위 원본을 티스토리용 AEO 최적화 블로그 포스트 JSON으로 변환하세요.
필드는 title, one_sentence_answer, markdown_body, faq(배열:{{question,answer}}), keywords(문자열 배열), meta_description 입니다.
- title: '{title_hint}' 스타일. 대표 키워드 "{primary_keyword}" 포함.
- markdown_body:
  · 소제목은 ##(H2)만. # H1 절대 금지(발행 시 title이 유일한 H1)
  · FAQ·이미지 문법(![]())·placeholder URL 금지
  · STT 포인트마다 구체 코칭 3문장 이상. 한 줄 요약 금지
  · "{primary_keyword}"를 markdown_body 본문에 완성된 문장 속 2~3회(서론·중반·마무리)
- one_sentence_answer: 핵심 1문장(키워드·학원명 자연 포함)
중요 포인트 녹음 STT가 여러 개면 하나의 레슨 일지로 모두 녹여 쓰고, 포인트별 구체적 내용이 빠지지 않게 하세요."""


def _parse_faq(raw: Any) -> list[FAQItem]:
    if not isinstance(raw, list):
        return []
    out: list[FAQItem] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question") or item.get("q") or "").strip()
        a = str(item.get("answer") or item.get("a") or "").strip()
        if q and a:
            out.append(FAQItem(question=q, answer=a))
    return out


def _article_from_parsed(parsed: dict[str, Any], academy: AcademyProfile) -> AEOArticle:
    keywords_raw = parsed.get("keywords")
    keywords = (
        [str(k).strip() for k in keywords_raw if str(k).strip()]
        if isinstance(keywords_raw, list)
        else []
    )
    return AEOArticle(
        title=str(parsed.get("title") or "").strip() or f"{academy.name} 레슨 기록",
        one_sentence_answer=str(
            parsed.get("one_sentence_answer") or parsed.get("oneSentenceAnswer") or ""
        ).strip(),
        markdown_body=_normalize_markdown_body(
            str(parsed.get("markdown_body") or parsed.get("markdownBody") or "")
        ),
        faq=_parse_faq(parsed.get("faq")),
        keywords=keywords,
        meta_description=str(
            parsed.get("meta_description") or parsed.get("metaDescription") or ""
        ).strip(),
    )


def optimize_source_to_aeo(
    source_text: str,
    academy: AcademyProfile,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    template_guide: str | None = None,
    keyword_plan: KeywordPlan | None = None,
) -> AEOArticle:
    """익명화된 sourceText → 티스토리 AEO JSON."""
    parsed = chat_json(
        api_key=api_key,
        model=model,
        system=get_aeo_system_prompt(getattr(academy, "industry", "general")),
        user=_build_source_text_prompt(
            source_text,
            academy,
            template_guide=template_guide,
            keyword_plan=keyword_plan,
        ),
        temperature=0.4,
    )
    return _article_from_parsed(parsed, academy)


def optimize_to_aeo(
    source: SourceContent,
    academy: AcademyProfile,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
) -> AEOArticle:
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key)

    industry = getattr(academy, "industry", "general")
    system_prompt = get_aeo_system_prompt(industry)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _build_user_prompt(source, academy)},
    ]

    # Structured Outputs (Pydantic) — 미지원 SDK는 JSON mode 폴백
    if hasattr(client.beta.chat.completions, "parse"):
        try:
            completion = client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=AEOArticle,
                temperature=0.4,
            )
            article = completion.choices[0].message.parsed
            if article is None:
                refusal = getattr(completion.choices[0].message, "refusal", None)
                raise RuntimeError(
                    f"OpenAI Structured Output 파싱 실패: {refusal or 'empty parsed'}"
                )
            return article
        except (AttributeError, TypeError) as exc:
            # parse API 시그니처 불일치 시에만 폴백
            print(f"  ! Structured Outputs 폴백 ({exc})")

    schema_hint = json.dumps(AEOArticle.model_json_schema(), ensure_ascii=False)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt
                + "\n\n반드시 다음 JSON Schema에 맞는 JSON만 출력하세요:\n"
                + schema_hint,
            },
            {"role": "user", "content": _build_user_prompt(source, academy)},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    raw = completion.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(raw)
    return AEOArticle.model_validate(data)


def article_to_markdown(article: AEOArticle) -> str:
    """발행용 전체 Markdown (제목 포함)."""
    parts = [f"# {article.title}", "", article.one_sentence_answer, "", article.markdown_body]
    if article.faq:
        parts.append("")
        parts.append("## 자주 묻는 질문")
        for item in article.faq:
            q, a = faq_qa(item)
            if not q:
                continue
            parts.append(f"### {q}")
            parts.append(a)
            parts.append("")
    return "\n".join(parts).strip() + "\n"


def faq_qa(item: FAQItem | dict[str, str]) -> tuple[str, str]:
    """FAQ 항목에서 question/answer를 안전하게 추출 (Pydantic | dict)."""
    if isinstance(item, FAQItem):
        return item.question, item.answer
    if isinstance(item, dict):
        return str(item.get("question") or ""), str(item.get("answer") or "")
    return str(getattr(item, "question", "") or ""), str(getattr(item, "answer", "") or "")
