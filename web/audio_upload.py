"""음성 파일 업로드·STT 처리 헬퍼."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import UploadFile

from core.stt import SUPPORTED_EXTENSIONS


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return suffix
    return ".webm"


async def save_uploaded_audio_files(files: list[UploadFile]) -> list[Path]:
    """업로드/녹음 파일을 임시 경로에 저장. 호출자가 cleanup_temp_audio_files로 삭제."""
    saved: list[Path] = []
    for upload in files:
        if not upload.filename:
            continue
        suffix = _safe_suffix(upload.filename)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await upload.read()
            if not content:
                continue
            tmp.write(content)
            saved.append(Path(tmp.name))
    return saved


def cleanup_temp_audio_files(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
