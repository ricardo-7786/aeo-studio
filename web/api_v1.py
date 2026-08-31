"""CODA → AEO HTTP API (v1)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from db.coda_connection import is_coda_db_configured
from db.connection import is_db_configured
from db.coda_repo import get_lesson_bundle, list_lessons
from services.coda_service import (
    dual_result_to_api_dict,
    generate_from_coda_json,
    generate_from_coda_lesson_id,
)

router = APIRouter(prefix="/api/v1", tags=["coda"])


class CodaSttSnippet(BaseModel):
    recording_id: int | str = Field(alias="recordingId", default=0)
    title: str = ""
    text: str = ""

    model_config = {"populate_by_name": True}


class CodaRecordingIn(BaseModel):
    recording_id: int | str = Field(alias="recordingId", default=0)
    title: str = ""
    audio_url: str = Field(alias="audioUrl", default="")
    processing_status: str = Field(alias="processingStatus", default="ready")
    created_at: str | None = Field(alias="createdAt", default=None)
    text: str = ""

    model_config = {"populate_by_name": True}


class CodaTagIn(BaseModel):
    timestamp_ms: int = Field(alias="timestampMs", default=0)
    type: str = ""
    note: str = ""

    model_config = {"populate_by_name": True}


class CodaGenerateRequest(BaseModel):
    academy_key: str = Field(alias="academyKey", default="")
    lesson_id: int | None = Field(alias="lessonId", default=None)
    lesson_title: str = Field(alias="lessonTitle", default="현장 기록")
    key_coaching_points: str = Field(alias="keyCoachingPoints", default="")
    teacher_name: str = Field(alias="teacherName", default="")
    academy_name: str = Field(alias="academyName", default="")
    student_real_name: str = Field(alias="studentRealName", default="")
    weekly_homework: str = Field(alias="weeklyHomework", default="")
    summary: str = ""
    include_stt: bool = Field(alias="includeStt", default=True)
    max_stt_clips: int = Field(alias="maxSttClips", default=12)
    stt_snippets: list[CodaSttSnippet] = Field(alias="sttSnippets", default_factory=list)
    recordings: list[CodaRecordingIn] = Field(default_factory=list)
    tags: list[CodaTagIn] = Field(default_factory=list)
    use_template: bool = Field(alias="useTemplate", default=False)
    target_keyword: str = Field(alias="targetKeyword", default="")
    template_channel: str = Field(alias="templateChannel", default="naver")
    manual_reference_urls: str = Field(alias="manualReferenceUrls", default="")
    force_template_refresh: bool = Field(alias="forceTemplateRefresh", default=False)
    focus_area: str = Field(alias="focusArea", default="")
    save_draft: bool = Field(alias="saveDraft", default=True)

    model_config = {"populate_by_name": True}


def _verify_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = (os.getenv("AEO_API_KEY") or "").strip()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization: Bearer <AEO_API_KEY> 필요")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="API 키가 올바르지 않습니다.")


def _lesson_row_dict(row) -> dict[str, Any]:
    return {
        "lessonId": row.lesson_id,
        "title": row.title,
        "teacherName": row.teacher_name,
        "studentName": row.student_name,
        "keyCoachingPoints": row.key_coaching_points,
        "summary": row.summary,
        "recordingCount": row.recording_count,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/coda/lessons")
async def coda_list_lessons(
    teacher: str = Query(default=""),
    limit: int = Query(default=40, ge=1, le=100),
    _: None = Depends(_verify_api_key),
) -> dict[str, Any]:
    if not is_coda_db_configured():
        raise HTTPException(status_code=503, detail="CODA_DATABASE_URL이 설정되지 않았습니다.")
    teacher_name = (teacher or os.getenv("CODA_TEACHER_NAME", "")).strip()
    try:
        rows = list_lessons(teacher_name=teacher_name, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"teacherName": teacher_name, "lessons": [_lesson_row_dict(r) for r in rows]}


@router.get("/coda/lessons/{lesson_id}")
async def coda_get_lesson(
    lesson_id: int,
    _: None = Depends(_verify_api_key),
) -> dict[str, Any]:
    if not is_coda_db_configured():
        raise HTTPException(status_code=503, detail="CODA_DATABASE_URL이 설정되지 않았습니다.")
    bundle = get_lesson_bundle(lesson_id)
    if not bundle:
        raise HTTPException(status_code=404, detail=f"CODA 레슨 #{lesson_id}을 찾을 수 없습니다.")
    return {
        **_lesson_row_dict(bundle.lesson),
        "recordings": [
            {
                "recordingId": r.recording_id,
                "title": r.title,
                "audioUrl": r.audio_url,
                "processingStatus": r.processing_status,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in bundle.recordings
        ],
        "tags": [
            {"timestampMs": t.timestamp_ms, "type": t.type, "note": t.note}
            for t in bundle.tags
        ],
    }


@router.post("/drafts/generate")
async def coda_generate_draft(
    body: CodaGenerateRequest,
    _: None = Depends(_verify_api_key),
) -> dict[str, Any]:
    gen_kwargs = dict(
        business_key=body.academy_key.strip() or None,
        save_to_db=body.save_draft and is_db_configured(),
        use_template=body.use_template,
        target_keyword=body.target_keyword,
        template_channel=body.template_channel,
        manual_reference_urls=body.manual_reference_urls,
        force_template_refresh=body.force_template_refresh,
        focus_area=body.focus_area.strip() or None,
    )
    try:
        if body.lesson_id is not None:
            result = generate_from_coda_lesson_id(
                body.lesson_id,
                extra_coaching=body.key_coaching_points.strip(),
                **gen_kwargs,
            )
        else:
            payload = body.model_dump(by_alias=True)
            result = generate_from_coda_json(payload, **gen_kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return dual_result_to_api_dict(result)


@router.get("/health")
async def api_health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "aeo-studio",
        "codaDb": "ok" if is_coda_db_configured() else "not_configured",
    }
