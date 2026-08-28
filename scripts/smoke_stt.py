#!/usr/bin/env python3
"""포인트 녹음 STT 스모크 테스트.

Usage:
  python scripts/smoke_stt.py --file ./recordings/point1.m4a
  python scripts/smoke_stt.py --file a.m4a --file b.m4a
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import load_settings
from core.stt import transcribe_audio


def main() -> int:
    p = argparse.ArgumentParser(description="Whisper STT smoke test")
    p.add_argument("--file", action="append", required=True, help="오디오 파일 (여러 번 가능)")
    args = p.parse_args()

    settings = load_settings()
    for f in args.file:
        path = Path(f)
        print(f"\n=== {path.name} ===")
        text = transcribe_audio(
            path,
            api_key=settings.openai_api_key,
            model=settings.whisper_model,
            language=settings.whisper_language,
        )
        print(text[:500] + ("..." if len(text) > 500 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
