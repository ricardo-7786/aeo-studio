"""티스토리(AEO) + 네이버(SEO) 동시 생성."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from config.settings import AcademyProfile
from core.aeo_optimizer import AEOArticle, article_to_markdown, optimize_source_to_aeo
from core.build_source import SttSnippet
from core.naver_optimizer import NaverBlogArticle, naver_article_to_plain, optimize_to_naver_seo
from core.schema_builder import build_json_ld


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


def optimize_dual_channels(
    source_text: str,
    academy: AcademyProfile,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    stt_snippets: list[SttSnippet] | None = None,
    template_guide: str | None = None,
) -> DualDraftResult:
    if not source_text.replace(" ", "").strip():
        raise ValueError(
            "AEO로 만들 내용이 없습니다. 핵심 코칭 포인트·STT 녹음 중 하나 이상을 남겨 주세요."
        )

    tistory = optimize_source_to_aeo(
        source_text,
        academy,
        api_key=api_key,
        model=model,
        template_guide=template_guide,
    )
    naver = optimize_to_naver_seo(
        source_text,
        academy,
        tistory,
        api_key=api_key,
        model=model,
        template_guide=template_guide,
    )
    markdown = article_to_markdown(tistory)
    json_ld = build_json_ld(academy, tistory)

    return DualDraftResult(
        tistory=tistory,
        markdown=markdown,
        naver=naver,
        naver_plain=naver_article_to_plain(naver),
        json_ld=json_ld,
        source_text=source_text,
        stt_snippets=stt_snippets or [],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
