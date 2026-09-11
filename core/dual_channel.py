"""티스토리(AEO) + 네이버(SEO) 동시 생성."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from config.settings import AcademyProfile
from core.aeo_optimizer import AEOArticle, article_to_markdown, optimize_source_to_aeo
from core.build_source import SttSnippet
from core.keyword_rotation import KeywordPlan, build_keyword_plan
from core.naver_optimizer import NaverBlogArticle, naver_article_to_plain, optimize_to_naver_seo
from core.schema_builder import build_json_ld
from core.stt_topic import (
    SttTopicPlan,
    detect_filler_phrases,
    detect_tistory_duplication,
    verify_key_point_coverage,
    verify_stt_contradictions,
    verify_topic_coverage,
)


@dataclass
class DualDraftResult:
    tistory: AEOArticle
    markdown: str
    naver: NaverBlogArticle
    naver_plain: str
    json_ld: dict
    source_text: str
    stt_snippets: list[SttSnippet]
    generated_at: str
    keyword_plan: KeywordPlan | None = None
    topic_plan: SttTopicPlan | None = None
    missing_topics: list[str] | None = None
    missing_key_points: list[str] | None = None
    filler_phrases: list[str] | None = None
    factual_warnings: list[str] | None = None
    duplicated_paragraphs: list[str] | None = None
    stt_review: list | None = None


def optimize_dual_channels(
    source_text: str,
    academy: AcademyProfile,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    stt_snippets: list[SttSnippet] | None = None,
    template_guide: str | None = None,
    keyword_plan: KeywordPlan | None = None,
    focus_area: str | None = None,
    lesson_title: str = "",
    target_keyword: str = "",
    topic_plan: SttTopicPlan | None = None,
    stt_review: list | None = None,
) -> DualDraftResult:
    if not source_text.replace(" ", "").strip():
        raise ValueError(
            "AEO로 만들 내용이 없습니다. 핵심 코칭 포인트·STT 녹음 중 하나 이상을 남겨 주세요."
        )

    plan = keyword_plan or build_keyword_plan(
        academy,
        source_text,
        focus_area_override=focus_area,
        lesson_title=lesson_title,
        target_keyword=target_keyword,
    )
    rotation_block = plan.prompt_block()
    combined_guide = "\n\n".join(p for p in (template_guide, rotation_block) if p)

    tistory = optimize_source_to_aeo(
        source_text,
        academy,
        api_key=api_key,
        model=model,
        template_guide=combined_guide,
        keyword_plan=plan,
        topic_plan=topic_plan,
    )
    naver = optimize_to_naver_seo(
        source_text,
        academy,
        tistory,
        api_key=api_key,
        model=model,
        template_guide=combined_guide,
        keyword_plan=plan,
        topic_plan=topic_plan,
    )
    markdown = article_to_markdown(tistory)
    json_ld = build_json_ld(academy, tistory)
    missing = verify_topic_coverage(
        topic_plan,
        tistory_text=markdown,
        naver_text=naver.body,
    )
    missing_kp = verify_key_point_coverage(
        topic_plan,
        tistory_text=markdown,
        naver_text=naver.body,
    )
    filler = detect_filler_phrases(f"{markdown}\n{naver.body}")
    factual = verify_stt_contradictions(source_text, f"{markdown}\n{naver.body}")
    dupes = detect_tistory_duplication(markdown, naver.body)

    return DualDraftResult(
        tistory=tistory,
        markdown=markdown,
        naver=naver,
        naver_plain=naver_article_to_plain(naver),
        json_ld=json_ld,
        source_text=source_text,
        stt_snippets=stt_snippets or [],
        generated_at=datetime.now(timezone.utc).isoformat(),
        keyword_plan=plan,
        topic_plan=topic_plan,
        missing_topics=missing or None,
        missing_key_points=missing_kp or None,
        filler_phrases=filler or None,
        factual_warnings=factual or None,
        duplicated_paragraphs=dupes or None,
        stt_review=stt_review,
    )
