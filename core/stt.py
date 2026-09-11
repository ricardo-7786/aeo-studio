"""음성 파일 → 텍스트 (OpenAI Whisper API). CODA server/aeo/stt.ts 포팅."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests
from openai import OpenAI

from core.audio_prep import ensure_whisper_ready
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
    prompt: str | None = None,
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

    use_path, temp_paths = ensure_whisper_ready(p)
    try:
        client = OpenAI(api_key=api_key)
        kwargs: dict = {
            "model": model,
            "file": None,
            "language": language,
            "response_format": "text",
        }
        if prompt and prompt.strip():
            kwargs["prompt"] = prompt.strip()[:800]
        with use_path.open("rb") as audio_file:
            kwargs["file"] = audio_file
            result = client.audio.transcriptions.create(**kwargs)
    finally:
        for tmp in temp_paths:
            tmp.unlink(missing_ok=True)

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
    prompt: str | None = None,
) -> str:
    """원격 오디오 URL → Whisper STT (CODA 레슨 녹음 URL용)."""
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 필요합니다 (STT).")

    res = requests.get(audio_url, timeout=120)
    res.raise_for_status()
    buf = res.content

    pathname = urlparse(audio_url).path
    ext = pathname.rsplit(".", 1)[-1] if "." in pathname else "webm"
    if ext.lower() not in {e.lstrip(".") for e in SUPPORTED_EXTENSIONS}:
        ext = "webm"

    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(buf)
        local_path = Path(tmp.name)

    try:
        return transcribe_audio(
            local_path,
            api_key=api_key,
            model=model,
            language=language,
            prompt=prompt,
        )
    finally:
        local_path.unlink(missing_ok=True)


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
