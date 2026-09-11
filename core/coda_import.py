"""CODA 레슨 녹음 → STT → sourceText (buildLessonSource.ts 포팅)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.build_source import LessonSourceInput, SttSnippet, build_anonymized_lesson_source
from core.stt import transcribe_audio_url


@dataclass
class CodaRecording:
    recording_id: int | str
    title: str = ""
    audio_url: str = ""
    processing_status: str = "ready"
    created_at: str | None = None
    text: str = ""  # STT 완료본이 있으면 URL 대신 사용


@dataclass
class CodaTag:
    timestamp_ms: int = 0
    type: str = ""
    note: str = ""


@dataclass
class CodaLessonPayload:
    lesson_title: str = "현장 기록"
    academy_key: str = ""
    key_coaching_points: str = ""
    teacher_name: str = ""
    academy_name: str = ""
    student_real_name: str = ""
    weekly_homework: str = ""
    summary: str = ""
    include_stt: bool = True
    max_stt_clips: int = 12
    recordings: list[CodaRecording] = field(default_factory=list)
    stt_snippets: list[SttSnippet] = field(default_factory=list)
    tags: list[CodaTag] = field(default_factory=list)


def pick_recordings_for_stt(recordings: list[CodaRecording], max_clips: int = 12) -> list[CodaRecording]:
    """ready + URL 클립 선정 (제목 있는 클립 우선, created_at 오름차순)."""
    ready = [
        r
        for r in recordings
        if (r.audio_url or "").strip()
        and (r.processing_status or "ready").lower() in {"", "ready"}
    ]
    with_title = [r for r in ready if (r.title or "").strip()]
    pool = list(with_title or ready)

    def _sort_key(r: CodaRecording) -> float:
        if not r.created_at:
            return 0.0
        try:
            return datetime.fromisoformat(r.created_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    pool.sort(key=_sort_key)
    n = max(0, max_clips)
    return pool[:n]


def _parse_recording(raw: dict) -> CodaRecording:
    return CodaRecording(
        recording_id=raw.get("recordingId") or raw.get("recording_id") or raw.get("id") or 0,
        title=str(raw.get("title") or "").strip(),
        audio_url=str(raw.get("audioUrl") or raw.get("audio_url") or "").strip(),
        processing_status=str(raw.get("processingStatus") or raw.get("processing_status") or "ready"),
        created_at=raw.get("createdAt") or raw.get("created_at"),
        text=str(raw.get("text") or "").strip(),
    )


def _parse_tag(raw: dict) -> CodaTag:
    return CodaTag(
        timestamp_ms=int(raw.get("timestampMs") or raw.get("timestamp_ms") or 0),
        type=str(raw.get("type") or ""),
        note=str(raw.get("note") or ""),
    )


def _parse_stt_snippet(raw: dict) -> SttSnippet:
    return SttSnippet(
        recording_id=raw.get("recordingId") or raw.get("recording_id") or 0,
        title=str(raw.get("title") or "").strip(),
        text=str(raw.get("text") or "").strip(),
    )


def parse_coda_payload(data: dict) -> CodaLessonPayload:
    """CODA API/JSON → CodaLessonPayload."""
    recordings = [_parse_recording(r) for r in (data.get("recordings") or []) if isinstance(r, dict)]
    stt_raw = data.get("sttSnippets") or data.get("stt_snippets") or []
    stt_snippets = [_parse_stt_snippet(s) for s in stt_raw if isinstance(s, dict)]
    tags = [_parse_tag(t) for t in (data.get("tags") or []) if isinstance(t, dict)]

    return CodaLessonPayload(
        lesson_title=str(
            data.get("lessonTitle") or data.get("lesson_title") or "현장 기록"
        ).strip(),
        academy_key=str(data.get("academyKey") or data.get("academy_key") or "").strip(),
        key_coaching_points=str(
            data.get("keyCoachingPoints") or data.get("key_coaching_points") or ""
        ).strip(),
        teacher_name=str(data.get("teacherName") or data.get("teacher_name") or "").strip(),
        academy_name=str(data.get("academyName") or data.get("academy_name") or "").strip(),
        student_real_name=str(
            data.get("studentRealName") or data.get("student_real_name") or ""
        ).strip(),
        weekly_homework=str(
            data.get("weeklyHomework") or data.get("weekly_homework") or ""
        ).strip(),
        summary=str(data.get("summary") or "").strip(),
        include_stt=bool(data.get("includeStt", data.get("include_stt", True))),
        max_stt_clips=int(data.get("maxSttClips") or data.get("max_stt_clips") or 12),
        recordings=recordings,
        stt_snippets=stt_snippets,
        tags=tags,
    )


def parse_recording_lines(raw: str) -> list[CodaRecording]:
    """한 줄에 하나: '제목|URL' 또는 URL만."""
    out: list[CodaRecording] = []
    for i, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        title = ""
        url = line
        if "|" in line:
            title, _, url = line.partition("|")
            title, url = title.strip(), url.strip()
        if not url.startswith("http"):
            continue
        out.append(CodaRecording(recording_id=i, title=title or f"포인트 {i}", audio_url=url))
    return out


def stt_from_coda_recordings(
    payload: CodaLessonPayload,
    *,
    api_key: str,
    whisper_model: str = "whisper-1",
    whisper_language: str = "ko",
    whisper_prompt: str | None = None,
) -> list[SttSnippet]:
    """pre-STT snippets + URL Whisper."""
    snippets: list[SttSnippet] = []
    for s in payload.stt_snippets:
        if s.text.strip():
            snippets.append(s)

    if payload.include_stt:
        clips = pick_recordings_for_stt(payload.recordings, payload.max_stt_clips)
        existing_ids = {str(s.recording_id) for s in snippets}
        for clip in clips:
            if str(clip.recording_id) in existing_ids:
                continue
            if clip.text.strip():
                snippets.append(
                    SttSnippet(
                        recording_id=clip.recording_id,
                        title=clip.title or f"녹음 #{clip.recording_id}",
                        text=clip.text,
                    )
                )
                continue
            try:
                text = transcribe_audio_url(
                    clip.audio_url,
                    api_key=api_key,
                    model=whisper_model,
                    language=whisper_language,
                    prompt=whisper_prompt,
                )
                snippets.append(
                    SttSnippet(
                        recording_id=clip.recording_id,
                        title=clip.title or f"녹음 #{clip.recording_id}",
                        text=text,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  ! CODA STT skip #{clip.recording_id}: {exc}")

    return snippets


def build_source_from_coda(payload: CodaLessonPayload, stt_snippets: list[SttSnippet]) -> str:
    tag_tuples = [
        (max(0, t.timestamp_ms // 1000), t.type, t.note) for t in payload.tags
    ]
    return build_anonymized_lesson_source(
        LessonSourceInput(
            lesson_title=payload.lesson_title,
            teacher_name=payload.teacher_name,
            academy_name=payload.academy_name,
            key_coaching_points=payload.key_coaching_points,
            tags=tag_tuples,
            stt_snippets=stt_snippets,
            weekly_homework=payload.weekly_homework,
            summary=payload.summary,
            student_real_name=payload.student_real_name,
        )
    )
