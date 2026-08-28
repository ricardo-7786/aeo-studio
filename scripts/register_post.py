"""발행 URL 등록 CLI."""

from __future__ import annotations

import argparse
import sys

from db.connection import is_db_configured
from db.post_repo import register_published_post


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="발행된 블로그 URL 등록 (순위 추적용)")
    p.add_argument("--business-key", required=True, help="업체 키")
    p.add_argument("--url", required=True, help="발행된 글 URL")
    p.add_argument(
        "--channel",
        required=True,
        choices=["naver", "tistory", "wordpress"],
        help="발행 채널",
    )
    p.add_argument("--keyword", default="", help="추적 키워드")
    p.add_argument(
        "--engine",
        default="naver",
        choices=["naver", "google"],
        help="검색 엔진",
    )
    p.add_argument("--draft-id", default="", help="연결할 aeo_drafts UUID (선택)")
    p.add_argument(
        "--no-monitor",
        action="store_true",
        help="순위 모니터링 비활성화",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    if not is_db_configured():
        print("DATABASE_URL이 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    try:
        post_id = register_published_post(
            business_key=args.business_key,
            channel=args.channel,
            published_url=args.url,
            target_keyword=args.keyword,
            target_engine=args.engine,
            draft_id=args.draft_id or None,
            is_monitored=not args.no_monitor,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"등록 완료: post_id={post_id}")


if __name__ == "__main__":
    main()
