#!/usr/bin/env python3
"""상위 노출 템플릿 추출 CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.template_service import get_or_build_template  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="키워드/URL → AEO 템플릿 JSON")
    p.add_argument("--keyword", required=True, help="타겟 키워드")
    p.add_argument("--channel", default="naver", choices=["naver", "google"])
    p.add_argument(
        "--url",
        action="append",
        dest="urls",
        default=[],
        help="수동 참고 URL (여러 번 지정 가능)",
    )
    p.add_argument("--force", action="store_true", help="캐시 무시하고 재추출")
    return p


def main() -> int:
    args = build_parser().parse_args()
    manual = "\n".join(args.urls) if args.urls else None
    try:
        template = get_or_build_template(
            target_keyword=args.keyword,
            channel=args.channel,
            manual_urls=manual,
            force_refresh=args.force,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(json.dumps(template.to_cache_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
