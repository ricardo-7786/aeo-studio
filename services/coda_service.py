"""CODA 레슨 → AEO/SEO 초안 생성."""

from __future__ import annotations

import json
from typing import Any

from config.settings import Settings, load_settings
from core.coda_import import (
    CodaLessonPayload,
    CodaRecording,
    CodaTag,
    build_source_from_coda,
    parse_coda_payload,
    parse_recording_lines,
    stt_from_coda_recordings,
)
from db.coda_repo import get_lesson_bundle
from core.dual_channel import DualDraftResult, optimize_dual_channels
from core.stt_topic import append_topic_plan_to_source, extract_stt_topic_plan
from services.content_service import GenerateResult, _save_draft_if_needed
from services.template_service import resolve_template_guide


def _merge_extra_coaching(payload: CodaLessonPayload, extra: str) -> CodaLessonPayload:
    extra = (extra or "").strip()
    if not extra:
        return payload
    merged = payload.key_coaching_points
    if merged:
        merged = f"{merged}\n{extra}"
    else:
        merged = extra
    return CodaLessonPayload(
        lesson_title=payload.lesson_title,
        academy_key=payload.academy_key,
        key_coaching_points=merged,
        teacher_name=payload.teacher_name,
        academy_name=payload.academy_name,
        student_real_name=payload.student_real_name,
        weekly_homework=payload.weekly_homework,
        summary=payload.summary,
        include_stt=payload.include_stt,
        max_stt_clips=payload.max_stt_clips,
        recordings=payload.recordings,
        stt_snippets=payload.stt_snippets,
        tags=payload.tags,
    )


def generate_from_coda(
    payload: CodaLessonPayload,
    *,
    business_key: str | None = None,
    save_to_db: bool = True,
    settings: Settings | None = None,
    use_template: bool = False,
    target_keyword: str = "",
    template_channel: str = "naver",
    manual_reference_urls: str = "",
    force_template_refresh: bool = False,
    focus_area: str | None = None,
    extra_coaching: str = "",
) -> GenerateResult:
    cfg = settings or load_settings(business_key=business_key or payload.academy_key or None)
    if not cfg.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    payload = _merge_extra_coaching(payload, extra_coaching)

    from core.lesson_subject import detect_lesson_subject, resolve_template_keyword
    from core.stt_music_review import prepare_theory_stt_snippets, resolve_whisper_prompt

    kw = (target_keyword or "").strip()
    rough_subject = detect_lesson_subject(
        cfg.business,
        lesson_title=payload.lesson_title,
        target_keyword=kw,
    )
    whisper_prompt = resolve_whisper_prompt(
        rough_subject, academy_services=cfg.business.services
    )
    stt_snippets = stt_from_coda_recordings(
        payload,
        api_key=cfg.openai_api_key,
        whisper_model=cfg.whisper_model,
        whisper_language=cfg.whisper_language,
        whisper_prompt=whisper_prompt,
    )
    stt_review: list = []
    review_block = ""
    if stt_snippets:
        stt_snippets, stt_review, review_block = prepare_theory_stt_snippets(
            stt_snippets,
            subject=rough_subject,
            lesson_title=payload.lesson_title,
            target_keyword=kw,
            academy_profile=cfg.business,
        )
    source_text = build_source_from_coda(payload, stt_snippets)
    if review_block:
        source_text = f"{source_text}\n\n{review_block}"
    if not source_text.replace(" ", ""):
        raise ValueError(
            "AEO로 만들 내용이 없습니다. CODA 녹음 URL·STT·핵심 코칭 포인트 중 하나 이상을 확인하세요."
        )

    from core.keyword_rotation import build_keyword_plan

    plan = build_keyword_plan(
        cfg.business,
        source_text,
        focus_area_override=focus_area,
        lesson_title=payload.lesson_title,
        target_keyword=(target_keyword or "").strip(),
    )
    resolved_keyword = resolve_template_keyword(plan, (target_keyword or "").strip())

    topic_plan = extract_stt_topic_plan(
        source_text,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        stt_snippets=stt_snippets or None,
    )
    if topic_plan:
        source_text = append_topic_plan_to_source(source_text, topic_plan)

    template_guide, template_obj = resolve_template_guide(
        use_template=use_template,
        target_keyword=resolved_keyword,
        template_channel=template_channel,
        manual_urls=manual_reference_urls,
        force_refresh=force_template_refresh,
        settings=cfg,
    )

    draft = optimize_dual_channels(
        source_text,
        cfg.business,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        stt_snippets=stt_snippets,
        template_guide=template_guide,
        keyword_plan=plan,
        focus_area=focus_area,
        lesson_title=payload.lesson_title,
        target_keyword=resolved_keyword,
        topic_plan=topic_plan,
        stt_review=stt_review or None,
    )
    title = payload.lesson_title.strip() or "현장 기록"
    draft_id = _save_draft_if_needed(
        draft=draft,
        profile=cfg.business,
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


def generate_from_coda_json(
    data: dict[str, Any],
    **kwargs: Any,
) -> GenerateResult:
    return generate_from_coda(parse_coda_payload(data), **kwargs)


def generate_from_coda_recording_urls(
    *,
    recording_lines: str,
    lesson_title: str = "현장 기록",
    key_coaching_points: str = "",
    teacher_name: str = "",
    include_stt: bool = True,
    **kwargs: Any,
) -> GenerateResult:
    recordings = parse_recording_lines(recording_lines)
    if not recordings:
        raise ValueError("CODA 녹음 URL을 한 줄에 하나씩 입력하세요. (형식: 제목|https://...)")
    payload = CodaLessonPayload(
        lesson_title=lesson_title,
        key_coaching_points=key_coaching_points,
        teacher_name=teacher_name,
        recordings=recordings,
        include_stt=include_stt,
    )
    return generate_from_coda(payload, **kwargs)


def dual_result_to_api_dict(result: GenerateResult) -> dict[str, Any]:
    d = result.draft
    return {
        "title": d.tistory.title,
        "oneSentenceAnswer": d.tistory.one_sentence_answer,
        "markdown": d.markdown,
        "naver": {
            "title": d.naver.title,
            "body": d.naver.body,
            "keywords": d.naver.keywords,
            "metaDescription": d.naver.meta_description,
        },
        "jsonLd": d.json_ld,
        "sourceText": d.source_text,
        "sttSnippets": [
            {"recordingId": s.recording_id, "title": s.title, "text": s.text}
            for s in d.stt_snippets
        ],
        "generatedAt": d.generated_at,
        "draftId": result.draft_id,
        "topicPlan": (
            {
                "topics": [
                    {"heading": t.heading, "keyPoints": t.key_points}
                    for t in d.topic_plan.topics
                ],
                "faqSuggestions": d.topic_plan.faq_suggestions,
                "suggestSplit": d.topic_plan.suggest_split,
                "splitHint": d.topic_plan.split_hint,
            }
            if d.topic_plan
            else None
        ),
        "missingTopics": d.missing_topics,
        "missingKeyPoints": d.missing_key_points,
        "fillerPhrases": d.filler_phrases,
        "sttReview": (
            [
                {
                    "severity": r.severity,
                    "category": r.category,
                    "message": r.message,
                    "excerpt": r.excerpt,
                }
                for r in d.stt_review
            ]
            if d.stt_review
            else None
        ),
        "keywordPlan": (
            {
                "focusArea": result.keyword_plan.focus_area,
                "titleHint": result.keyword_plan.title_hint,
            }
            if result.keyword_plan
            else None
        ),
    }


def payload_from_coda_lesson_id(lesson_id: int) -> CodaLessonPayload:
    bundle = get_lesson_bundle(lesson_id)
    if not bundle:
        raise ValueError(f"CODA 레sson #{lesson_id}을 찾을 수 없습니다.")
    if not bundle.recordings:
        raise ValueError(f"CODA 레sson #{lesson_id}에 audio_url 녹음이 없습니다.")

    return CodaLessonPayload(
        lesson_title=bundle.lesson.title or "현장 기록",
        key_coaching_points=bundle.lesson.key_coaching_points,
        teacher_name=bundle.lesson.teacher_name,
        student_real_name=bundle.lesson.student_name,
        summary=bundle.lesson.summary,
        recordings=[
            CodaRecording(
                recording_id=r.recording_id,
                title=r.title or f"녹음 #{r.recording_id}",
                audio_url=r.audio_url,
                processing_status=r.processing_status,
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
            for r in bundle.recordings
        ],
        tags=[
            CodaTag(timestamp_ms=t.timestamp_ms, type=t.type, note=t.note)
            for t in bundle.tags
        ],
    )


def generate_from_coda_lesson_id(
    lesson_id: int,
    **kwargs: Any,
) -> GenerateResult:
    payload = payload_from_coda_lesson_id(lesson_id)
    return generate_from_coda(payload, **kwargs)


def parse_coda_json_text(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("CODA JSON이 비어 있습니다.")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("CODA JSON은 객체여야 합니다.")
    return data
