"""콘텐츠 생성·저장 통합 서비스."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings, load_settings
from core.build_source import build_source_from_stt_only
from core.draft_generator import transcribe_audio_paths
from core.dual_channel import DualDraftResult, optimize_dual_channels
from core.keyword_rotation import KeywordPlan, build_keyword_plan
from core.lesson_subject import detect_lesson_subject, resolve_template_keyword
from core.stt_music_review import prepare_theory_stt_snippets, resolve_whisper_prompt
from core.stt_topic import append_topic_plan_to_source, extract_stt_topic_plan
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
    keyword_plan: KeywordPlan | None = None


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
    focus_area: str | None = None,
) -> GenerateResult:
    cfg = settings or load_settings(business_key=business_key, industry_override=industry)
    profile = cfg.business
    title = lesson_title.strip() or "현장 기록"
    kw = (target_keyword or "").strip()
    memo = source_text.strip()
    paths = [Path(p) for p in (audio_paths or []) if str(p).strip()]

    if not cfg.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    stt_snippets = []
    stt_review = []
    plan_source = memo

    if paths:
        rough_subject = detect_lesson_subject(
            profile, lesson_title=title, target_keyword=kw
        )
        whisper_prompt = resolve_whisper_prompt(
            rough_subject, academy_services=profile.services
        )
        stt_snippets = transcribe_audio_paths(
            paths,
            api_key=cfg.openai_api_key,
            whisper_model=cfg.whisper_model,
            whisper_language=cfg.whisper_language,
            whisper_prompt=whisper_prompt,
        )
        if not stt_snippets:
            raise ValueError(
                "업로드된 음성에서 STT 결과를 얻지 못했습니다. "
                "파일이 비어 있거나 형식을 확인하세요."
            )
        stt_snippets, stt_review, review_block = prepare_theory_stt_snippets(
            stt_snippets,
            subject=rough_subject,
            lesson_title=title,
            target_keyword=kw,
            academy_profile=profile,
        )
        plan_source = build_source_from_stt_only(
            lesson_title=title,
            stt_snippets=stt_snippets,
            key_coaching_points=memo,
            academy_name=profile.name,
        )
        if review_block:
            plan_source = f"{plan_source}\n\n{review_block}"

    preview_plan = build_keyword_plan(
        profile,
        plan_source,
        focus_area_override=focus_area,
        lesson_title=title,
        target_keyword=kw,
    )
    resolved_keyword = resolve_template_keyword(preview_plan, kw)

    topic_plan = extract_stt_topic_plan(
        plan_source,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        stt_snippets=stt_snippets or None,
    )
    if topic_plan:
        plan_source = append_topic_plan_to_source(plan_source, topic_plan)

    template_guide, template_obj = resolve_template_guide(
        use_template=use_template,
        target_keyword=resolved_keyword,
        template_channel=template_channel,
        manual_urls=manual_reference_urls,
        force_refresh=force_template_refresh,
        settings=cfg,
    )

    if paths:
        draft = optimize_dual_channels(
            plan_source,
            profile,
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            stt_snippets=stt_snippets,
            template_guide=template_guide,
            keyword_plan=preview_plan,
            focus_area=focus_area,
            lesson_title=title,
            target_keyword=resolved_keyword,
            topic_plan=topic_plan,
            stt_review=stt_review or None,
        )
    elif memo.replace(" ", ""):
        draft = optimize_dual_channels(
            plan_source,
            profile,
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            template_guide=template_guide,
            keyword_plan=preview_plan,
            focus_area=focus_area,
            lesson_title=title,
            target_keyword=resolved_keyword,
            topic_plan=topic_plan,
            stt_review=stt_review or None,
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
        keyword_plan=draft.keyword_plan,
    )
