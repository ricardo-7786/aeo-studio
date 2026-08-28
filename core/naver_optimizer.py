"""네이버 블로그 SEO 초안 생성 — CODA optimizeLessonToNaverSeo 포팅."""

from __future__ import annotations

from pydantic import BaseModel, Field

from config.settings import AcademyProfile
from core.aeo_optimizer import AEOArticle, article_to_markdown, academy_context_block
from core.naver_utils import build_naver_local_keywords, normalize_naver_title, strip_naver_markdown
from core.openai_json import chat_json
from core.prompts import get_naver_system_prompt


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
) -> NaverBlogArticle:
    local_keywords = build_naver_local_keywords(academy)
    tistory_plain = article_to_markdown(tistory_article)
    kw0 = local_keywords[0] if local_keywords else academy.name
    guide_block = f"\n\n{template_guide}\n" if template_guide else ""

    user_prompt = f"""{academy_context_block(academy)}
{guide_block}
[네이버 SEO 필수 지역 키워드 — 제목·본문에 자연스럽게 사용]
{chr(10).join(f"{i + 1}. {k}" for i, k in enumerate(local_keywords))}

[원본 — 레슨 기록 (익명화됨)]
{source_text}

[티스토리/AEO용 원고 — 이와 문장·구조 20% 이상 다르게 쓸 것]
{tistory_plain}

위 원본을 네이버 블로그 SEO용 JSON으로 작성하세요.
필드는 title, body, keywords(문자열 배열), meta_description 입니다.
- title: [지역키워드] + [레슨 곡명/실제 고민] + [해결·후기 톤]. 키워드만 나열 금지. 최대 58자. 학원명 최대 1회.
  예) "{kw0} 레슨 일지: '그겨울' 고음 발음이 자꾸 씹힐 때 해결법"
- body (짧게 쓰지 말 것):
  · 단락 최소 5개(권장 6~8), 공백 제외 약 700자 이상
  · STT 클립마다: 소리 문제 1문장 + 코칭 팁 2문장 이상, 가사/곡명 생생히. 클립당 최소 1단락
  · 총평 금지(자신감/연습하면/유익한 시간/진행되었답니다 등). 구체 팁으로 끝내기
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

    fallback_title = f"{kw0} 레슨 후기"
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
