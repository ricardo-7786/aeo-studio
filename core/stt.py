"""음성 파일 → 텍스트 (OpenAI Whisper API). CODA server/aeo/stt.ts 포팅."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests
from openai import OpenAI

from core.input_parser import SourceContent, make_source

SUPPORTED_EXTENSIONS = {
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".m4a",
    ".wav",
    ".webm",
    ".ogg",
}


def transcribe_audio(
    path: str | Path,
    *,
    api_key: str,
    model: str = "whisper-1",
    language: str = "ko",
) -> str:
    """로컬 레슨 음성 메모를 한국어 텍스트로 변환."""
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {path}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 형식입니다 ({p.suffix}). "
            f"지원: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if p.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Whisper API는 파일당 25MB 이하만 지원합니다.")

    client = OpenAI(api_key=api_key)
    with p.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            language=language,
            response_format="text",
        )

    text = (result if isinstance(result, str) else str(result)).strip()
    if not text:
        raise ValueError("음성에서 텍스트를 추출하지 못했습니다. 녹음 길이·음량을 확인하세요.")
    return text


def transcribe_audio_url(
    audio_url: str,
    *,
    api_key: str,
    model: str = "whisper-1",
    language: str = "ko",
) -> str:
    """원격 오디오 URL → Whisper STT (CODA 레슨 녹음 URL용)."""
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 필요합니다 (STT).")

    res = requests.get(audio_url, timeout=120)
    res.raise_for_status()
    buf = res.content
    if len(buf) > 24 * 1024 * 1024:
        raise ValueError("오디오가 너무 큽니다 (25MB 제한). 짧은 포인트 녹음을 사용하세요.")

    pathname = urlparse(audio_url).path
    ext = pathname.rsplit(".", 1)[-1] if "." in pathname else "webm"
    filename = f"lesson-clip.{ext}"
    mime = {
        "mp3": "audio/mpeg",
        "mpeg": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
    }.get(ext.lower(), "audio/webm")

    client = OpenAI(api_key=api_key)
    from io import BytesIO

    bio = BytesIO(buf)
    bio.name = filename  # type: ignore[attr-defined]
    result = client.audio.transcriptions.create(
        model=model,
        file=(filename, bio, mime),
        language=language,
        response_format="text",
    )
    text = (result if isinstance(result, str) else str(result)).strip()
    if not text:
        raise ValueError("STT 결과가 비어 있습니다.")
    return text


def transcribe_many(
    paths: list[str | Path],
    *,
    api_key: str,
    model: str = "whisper-1",
    language: str = "ko",
    titles: list[str] | None = None,
) -> list[tuple[str, str]]:
    """여러 포인트 녹음 STT. (title, text) 목록 반환."""
    out: list[tuple[str, str]] = []
    for i, path in enumerate(paths):
        p = Path(path)
        label = (titles[i] if titles and i < len(titles) else "") or p.stem or f"포인트 {i + 1}"
        text = transcribe_audio(p, api_key=api_key, model=model, language=language)
        out.append((label, text))
    return out


def load_audio(path: str | Path, *, api_key: str, model: str = "whisper-1", language: str = "ko") -> SourceContent:
    """음성 파일 STT 후 SourceContent 반환."""
    p = Path(path)
    text = transcribe_audio(p, api_key=api_key, model=model, language=language)
    return make_source(
        title=f"음성 메모 ({p.stem})",
        body=text,
        source_type="audio",
        source_ref=str(p.resolve()),
    )
