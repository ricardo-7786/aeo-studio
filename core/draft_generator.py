"""STT → sourceText → dual channel 초안 — CODA generateAeoDraft.ts 포팅."""

from __future__ import annotations

from pathlib import Path

from config.settings import AcademyProfile
from core.build_source import SttSnippet, build_source_from_stt_only
from core.dual_channel import DualDraftResult, optimize_dual_channels
from core.stt import transcribe_audio


def transcribe_audio_paths(
    audio_paths: list[str | Path],
    *,
    api_key: str,
    whisper_model: str = "whisper-1",
    whisper_language: str = "ko",
    whisper_prompt: str | None = None,
    titles: list[str] | None = None,
) -> list[SttSnippet]:
    """여러 음성 파일 → STT snippets (생성 전 과목·키워드 판별용)."""
    stt_snippets: list[SttSnippet] = []
    errors: list[str] = []
    for i, path in enumerate(audio_paths):
        p = Path(path)
        label = (titles[i] if titles and i < len(titles) else "") or p.stem or f"포인트 {i + 1}"
        try:
            text = transcribe_audio(
                p,
                api_key=api_key,
                model=whisper_model,
                language=whisper_language,
                prompt=whisper_prompt,
            )
            stt_snippets.append(SttSnippet(recording_id=i + 1, title=label, text=text))
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).strip() or exc.__class__.__name__
            size_mb = p.stat().st_size / (1024 * 1024) if p.is_file() else 0
            errors.append(f"{label}: {msg}" + (f" ({size_mb:.1f}MB)" if size_mb else ""))
            print(f"  ! STT skip {p.name}: {msg}")

    if not stt_snippets and errors:
        raise ValueError(
            "음성 STT에 실패했습니다.\n" + "\n".join(f"· {e}" for e in errors)
        )
    return stt_snippets


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
    focus_area: str | None = None,
) -> DualDraftResult:
    """여러 포인트 녹음 → STT → 하나의 블로그 초안(티스토리+네이버)."""
    stt_snippets = transcribe_audio_paths(
        audio_paths,
        api_key=api_key,
        whisper_model=whisper_model,
        whisper_language=whisper_language,
        titles=titles,
    )
    if not stt_snippets:
        raise ValueError("음성 STT에 실패했습니다. 파일 형식·용량을 확인하세요.")

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
        focus_area=focus_area,
        lesson_title=lesson_title,
    )


def generate_draft_from_source_text(
    source_text: str,
    academy: AcademyProfile,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    template_guide: str | None = None,
    focus_area: str | None = None,
    lesson_title: str = "",
    target_keyword: str = "",
) -> DualDraftResult:
    return optimize_dual_channels(
        source_text,
        academy,
        api_key=api_key,
        model=model,
        template_guide=template_guide,
        focus_area=focus_area,
        lesson_title=lesson_title,
        target_keyword=target_keyword,
    )
