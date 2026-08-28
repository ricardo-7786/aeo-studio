"""STT → sourceText → dual channel 초안 — CODA generateAeoDraft.ts 포팅."""

from __future__ import annotations

from pathlib import Path

from config.settings import AcademyProfile
from core.build_source import SttSnippet, build_source_from_stt_only
from core.dual_channel import DualDraftResult, optimize_dual_channels
from core.stt import transcribe_audio


def generate_draft_from_audio_files(
    *,
    audio_paths: list[str | Path],
    lesson_title: str,
    academy: AcademyProfile,
    api_key: str,
    model: str = "gpt-4o-mini",
    whisper_model: str = "whisper-1",
    whisper_language: str = "ko",
    titles: list[str] | None = None,
    key_coaching_points: str = "",
    template_guide: str | None = None,
) -> DualDraftResult:
    """여러 포인트 녹음 → STT → 하나의 블로그 초안(티스토리+네이버)."""
    stt_snippets: list[SttSnippet] = []
    for i, path in enumerate(audio_paths):
        p = Path(path)
        label = (titles[i] if titles and i < len(titles) else "") or p.stem or f"포인트 {i + 1}"
        try:
            text = transcribe_audio(
                p,
                api_key=api_key,
                model=whisper_model,
                language=whisper_language,
            )
            stt_snippets.append(SttSnippet(recording_id=i + 1, title=label, text=text))
        except Exception as exc:  # noqa: BLE001 — 클립별 STT 실패는 건너뜀
            print(f"  ! STT skip {p.name}: {exc}")

    source_text = build_source_from_stt_only(
        lesson_title=lesson_title,
        stt_snippets=stt_snippets,
        key_coaching_points=key_coaching_points,
        academy_name=academy.name,
    )

    return optimize_dual_channels(
        source_text,
        academy,
        api_key=api_key,
        model=model,
        stt_snippets=stt_snippets,
        template_guide=template_guide,
    )


def generate_draft_from_source_text(
    source_text: str,
    academy: AcademyProfile,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
) -> DualDraftResult:
    return optimize_dual_channels(source_text, academy, api_key=api_key, model=model)
