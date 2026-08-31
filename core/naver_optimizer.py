"""네이버 블로그 SEO 초안 생성 — CODA optimizeLessonToNaverSeo 포팅."""

from __future__ import annotations

from pydantic import BaseModel, Field

from config.settings import AcademyProfile
from core.aeo_optimizer import AEOArticle, article_to_markdown, academy_context_block
from core.keyword_rotation import KeywordPlan
from core.naver_utils import build_naver_local_keywords, normalize_naver_title, strip_naver_markdown
from core.openai_json import chat_json
from core.prompts import (
    get_naver_system_prompt,
    keyword_density_block,
    positive_style_block,
    strict_negative_block,
)
from core.template.prompt_block import resolve_naver_target_chars


class NaverBlogArticle(BaseModel):
    title: str
    body: str
    keywords: list[str] = Field(default_factory=list)
    meta_description: str = ""


def optimize_to_naver_seo(
    source_text: str,
    academy: AcademyProfile,
    tistory_article: AEOArticle,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    template_guide: str | None = None,
    keyword_plan: KeywordPlan | None = None,
) -> NaverBlogArticle:
    local_keywords = build_naver_local_keywords(academy)
    if keyword_plan:
        rotated = [
            keyword_plan.title_keyword,
            f"{keyword_plan.focus_area} {academy.services[0]}" if academy.services else keyword_plan.focus_area,
        ]
        if keyword_plan.problem_keywords:
            rotated.append(f"{keyword_plan.focus_area} {keyword_plan.problem_keywords[0]}")
        local_keywords = [k for k in rotated if k] + [k for k in local_keywords if k not in rotated]
    tistory_plain = article_to_markdown(tistory_article)
    kw0 = local_keywords[0] if local_keywords else academy.name
    primary_keyword = keyword_plan.title_keyword if keyword_plan else kw0
    guide_block = f"\n\n{template_guide}\n" if template_guide else ""
    target_chars = resolve_naver_target_chars(template_guide)
    has_template = bool(template_guide and template_guide.strip())
    min_paragraphs = "6~8" if has_template else "5"
    length_rule = (
        f"공백 제외 약 {target_chars}자 목표(최소 1,500자, 최대 2,000자). "
        "원문·학원 프로필 사실로만 채울 것."
        if has_template
        else "공백 제외 약 700자 이상"
    )
    evidence_block = ""
    if academy.evidence.strip():
        evidence_block = f"""
[학원 고정 사실 — 원문 STT에 없어도 아래만 사용 가능. 지어내기·과장 금지]
- {academy.evidence}
- 위 내용을 레슨 스토리와 자연스럽게 1~2단락 연결(시설·시스템·강점). 원문과 모순 금지."""
    title_example = (
        keyword_plan.title_hint
        if keyword_plan
        else f"{kw0} 레슨 일지: '그겨울' 고음 발음이 자꾸 씹힐 때 해결법"
    )

    user_prompt = f"""{academy_context_block(academy)}
{guide_block}
{evidence_block}
{keyword_density_block(primary_keyword)}
{strict_negative_block()}
{positive_style_block()}

[네이버 SEO 필수 지역 키워드 — 제목·본문에 자연스럽게 사용]
{chr(10).join(f"{i + 1}. {k}" for i, k in enumerate(local_keywords))}

[원본 — 레슨 기록 (익명화됨)]
{source_text}

[티스토리/AEO용 원고 — 이와 문장·구조 20% 이상 다르게 쓸 것]
{tistory_plain}

위 원본을 네이버 블로그 SEO용 JSON으로 작성하세요.
필드는 title, body, keywords(문자열 배열), meta_description 입니다.
- title: [지역키워드] + [레슨 곡명/실제 고민] + [해결·후기 톤]. 키워드만 나열 금지. 최대 58자. 학원명 최대 1회.
  예) "{title_example}"
- body (짧게 쓰지 말 것):
  · 단락 최소 {min_paragraphs}개, {length_rule}
  · STT/메모 포인트마다: 현장 상황 1문장 + 코칭 지시·관찰 3문장 이상(한 줄 요약 금지). 클립·주제당 최소 1단락
  · 대표 타깃 키워드 "{primary_keyword}": body에 완성된 문장 속 약 3회(서론·중반 레슨·마무리 위치). 키워드 나열·도배 금지
  · '서론', '문제 제기', '결심', '마무리' 등 템플릿 단계명을 소제목·단락 제목으로 쓰지 말 것. 스토리형 문장으로 전개
  · 원문에 없는 코칭 디테일(횡격막·자세·장비 등)을 지어내지 말 것. 모르면 [학원 고정 사실]·연락처·통학 맥락으로 분량 보완
  · 총평·감상문 금지. 마지막도 구체 팁·다음 레슨 포인트로 끝내기
  · [사진 추천: …] 서로 다른 단락 직후 3곳(한 줄에 장면 나열·맨 아래 몰기 금지)
  · 마크다운 금지. 연락처는 "전화: … / 주소: … / 웹사이트: https://…" 일반 텍스트
- keywords: 지역 키워드 + 학원명·서비스·곡/문제 태그
티스토리와 표현을 다르게 하되 STT 디테일은 네이버에 더 풍부하게 펼치세요."""

    parsed = chat_json(
        api_key=api_key,
        model=model,
        system=get_naver_system_prompt(getattr(academy, "industry", "general")),
        user=user_prompt,
        temperature=0.72,
    )

    raw_body = str(
        parsed.get("body") or parsed.get("markdown_body") or parsed.get("markdownBody") or ""
    ).strip()
    fallback_body = (
        f"{kw0}에서 진행한 레슨 기록입니다.\n\n[사진 추천: 레슨실 내부 또는 악보 이미지]\n"
    )
    body = strip_naver_markdown(raw_body or fallback_body)

    keywords_raw = parsed.get("keywords")
    keywords = (
        [str(k).strip() for k in keywords_raw if str(k).strip()]
        if isinstance(keywords_raw, list)
        else local_keywords
    )
    if not keywords:
        keywords = local_keywords

    fallback_title = keyword_plan.title_hint if keyword_plan else f"{kw0} 레슨 후기"
    title = normalize_naver_title(str(parsed.get("title") or ""), fallback_title)

    return NaverBlogArticle(
        title=title,
        body=body,
        keywords=keywords,
        meta_description=str(
            parsed.get("meta_description") or parsed.get("metaDescription") or ""
        ).strip(),
    )


def naver_article_to_plain(article: NaverBlogArticle) -> str:
    return f"{article.title}\n\n{article.body.strip()}\n"
