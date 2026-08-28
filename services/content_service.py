"""콘텐츠 생성·저장 통합 서비스."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings, load_settings
from core.dual_channel import DualDraftResult, optimize_dual_channels
from core.draft_generator import generate_draft_from_audio_files
from core.template.models import AeoTemplate
from db.connection import is_db_configured
from db.draft_repo import save_aeo_draft
from services.template_service import resolve_template_guide


@dataclass
class GenerateResult:
    draft: DualDraftResult
    draft_id: str | None
    lesson_title: str
    template: AeoTemplate | None = None


def _save_draft_if_needed(
    *,
    draft: DualDraftResult,
    profile,
    lesson_title: str,
    save_to_db: bool,
) -> str | None:
    if not save_to_db or not is_db_configured():
        return None
    stt_payload = [
        {"recording_id": s.recording_id, "title": s.title, "text": s.text}
        for s in draft.stt_snippets
    ]
    return save_aeo_draft(
        business_key=profile.business_key,
        lesson_title=lesson_title,
        source_text=draft.source_text,
        tistory_markdown=draft.markdown,
        json_ld=draft.json_ld,
        naver_title=draft.naver.title,
        naver_body=draft.naver_plain,
        naver_keywords=draft.naver.keywords,
        stt_snippets=stt_payload,
    )


def generate_dual_draft(
    *,
    source_text: str = "",
    audio_paths: list[str | Path] | None = None,
    lesson_title: str = "현장 기록",
    business_key: str | None = None,
    industry: str | None = None,
    save_to_db: bool = True,
    settings: Settings | None = None,
    use_template: bool = False,
    target_keyword: str = "",
    template_channel: str = "naver",
    manual_reference_urls: str = "",
    force_template_refresh: bool = False,
) -> GenerateResult:
    cfg = settings or load_settings(business_key=business_key, industry_override=industry)
    profile = cfg.business
    title = lesson_title.strip() or "현장 기록"

    if not cfg.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    template_guide, template_obj = resolve_template_guide(
        use_template=use_template,
        target_keyword=target_keyword,
        template_channel=template_channel,
        manual_urls=manual_reference_urls,
        force_refresh=force_template_refresh,
        settings=cfg,
    )

    text = source_text.strip()
    paths = [Path(p) for p in (audio_paths or []) if str(p).strip()]

    if paths:
        draft = generate_draft_from_audio_files(
            audio_paths=paths,
            lesson_title=title,
            academy=profile,
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            whisper_model=cfg.whisper_model,
            whisper_language=cfg.whisper_language,
            key_coaching_points=text,
            template_guide=template_guide,
        )
    elif text.replace(" ", ""):
        draft = optimize_dual_channels(
            text,
            profile,
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            template_guide=template_guide,
        )
    else:
        raise ValueError("현장 메모, 음성 파일 업로드, 또는 앱 내 녹음 중 하나 이상을 입력하세요.")

    draft_id = _save_draft_if_needed(
        draft=draft,
        profile=profile,
        lesson_title=title,
        save_to_db=save_to_db,
    )
    return GenerateResult(
        draft=draft,
        draft_id=draft_id,
        lesson_title=title,
        template=template_obj,
    )
