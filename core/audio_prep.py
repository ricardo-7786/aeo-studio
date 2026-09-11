"""Whisper STT용 음성 전처리 — 25MB 초과 시 ffmpeg 압축."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

WHISPER_MAX_BYTES = 25 * 1024 * 1024
_SPEECH_BITRATES = ("32k", "24k", "16k")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run_ffmpeg(src: Path, dst: Path, *, bitrate: str) -> None:
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        bitrate,
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail or f"ffmpeg 실패 (exit {proc.returncode})")


def compress_audio_for_speech(src: Path) -> Path:
    """음성 STT용 mono 16kHz MP3로 압축. 출력 경로 반환."""
    if not ffmpeg_available():
        size_mb = src.stat().st_size / (1024 * 1024)
        raise ValueError(
            f"파일이 {size_mb:.1f}MB로 Whisper 한도(25MB)를 초과합니다. "
            "ffmpeg가 없어 자동 압축할 수 없습니다. "
            "짧게 잘라 업로드하거나 `brew install ffmpeg` 후 다시 시도하세요."
        )

    last_error: Exception | None = None
    for bitrate in _SPEECH_BITRATES:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            out = Path(tmp.name)
        try:
            _run_ffmpeg(src, out, bitrate=bitrate)
            if out.stat().st_size <= WHISPER_MAX_BYTES:
                return out
            out.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            out.unlink(missing_ok=True)

    if last_error:
        raise ValueError(
            f"압축 후에도 25MB를 초과합니다. 더 짧은 구간으로 나눠 업로드하세요. ({last_error})"
        ) from last_error
    raise ValueError("압축 후에도 25MB를 초과합니다. 더 짧은 구간으로 나눠 업로드하세요.")


def ensure_whisper_ready(path: Path) -> tuple[Path, list[Path]]:
    """
    Whisper API에 넣을 수 있는 경로 반환.
    압축 파일을 만들었으면 두 번째 값에 정리할 임시 경로 목록.
    """
    p = path.resolve()
    if not p.is_file():
        raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {path}")
    if p.stat().st_size <= WHISPER_MAX_BYTES:
        return p, []

    compressed = compress_audio_for_speech(p)
    return compressed, [compressed]
