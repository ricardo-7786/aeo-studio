#!/usr/bin/env python3
"""업체(워크스pace) 관리 CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import _profile_from_env  # noqa: E402
from config.industry import INDUSTRIES  # noqa: E402
from db.business_repo import BusinessRepo, BusinessRow  # noqa: E402
from db.connection import is_db_configured  # noqa: E402


def _print_row(row: BusinessRow) -> None:
    print(f"  key      : {row.business_key}")
    print(f"  industry : {row.industry}")
    print(f"  name     : {row.name}")
    print(f"  location : {row.location}")
    print(f"  phone    : {row.phone}")
    print(f"  url      : {row.url}")
    print(f"  services : {row.services}")
    print(f"  evidence : {row.evidence[:80]}{'…' if len(row.evidence) > 80 else ''}")


def cmd_list(_: argparse.Namespace) -> int:
    repo = BusinessRepo()
    rows = repo.list_all()
    if not rows:
        print("(등록된 업체 없음)")
        return 0
    for row in rows:
        print(f"- {row.business_key} [{row.industry}] {row.name}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    row = BusinessRepo().get(args.key)
    if not row:
        print(f"[ERROR] 업체 없음: {args.key}", file=sys.stderr)
        return 1
    _print_row(row)
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    row = BusinessRow(
        business_key=args.key,
        industry=args.industry,
        name=args.name or args.key,
        location=args.location or "",
        address=args.address or "",
        phone=args.phone or "",
        url=args.url or "",
        services=args.services or "",
        evidence=args.evidence or "",
        geo_lat=args.geo_lat,
        geo_lng=args.geo_lng,
        price_range=args.price_range or "$$",
        opening_hours=args.opening_hours or "",
    )
    saved = BusinessRepo().upsert(row)
    print("저장됨:")
    _print_row(saved)
    return 0


def cmd_seed_env(_: argparse.Namespace) -> int:
    profile = _profile_from_env()
    row = BusinessRow(
        business_key=profile.business_key,
        industry=profile.industry,
        name=profile.name,
        location=profile.location,
        address=profile.address,
        phone=profile.phone,
        url=profile.url,
        services=", ".join(profile.services),
        evidence=profile.evidence,
        geo_lat=str(profile.geo_lat) if profile.geo_lat else None,
        geo_lng=str(profile.geo_lng) if profile.geo_lng else None,
        price_range=profile.price_range,
        opening_hours=profile.opening_hours,
    )
    saved = BusinessRepo().upsert(row)
    print(".env → DB 시드 완료:")
    _print_row(saved)
    return 0


def main() -> int:
    if not is_db_configured():
        print("[ERROR] DATABASE_URL을 .env에 설정하세요.", file=sys.stderr)
        return 1

    p = argparse.ArgumentParser(description="AEO 업체(워크스페이스) 관리")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="업체 목록")

    show_p = sub.add_parser("show", help="업체 상세")
    show_p.add_argument("--key", required=True)

    add_p = sub.add_parser("add", help="업체 등록/수정")
    add_p.add_argument("--key", required=True, help="고유 키 (예: 화정역-보컬학원)")
    add_p.add_argument("--name", default="")
    add_p.add_argument("--industry", default="general", choices=INDUSTRIES)
    add_p.add_argument("--location", default="")
    add_p.add_argument("--address", default="")
    add_p.add_argument("--phone", default="")
    add_p.add_argument("--url", default="")
    add_p.add_argument("--services", default="")
    add_p.add_argument("--evidence", default="")
    add_p.add_argument("--geo-lat", default=None)
    add_p.add_argument("--geo-lng", default=None)
    add_p.add_argument("--price-range", default="$$")
    add_p.add_argument("--opening-hours", default="")

    sub.add_parser("seed-from-env", help=".env ACADEMY_*/BUSINESS_* → DB")

    args = p.parse_args()
    handlers = {
        "list": cmd_list,
        "show": cmd_show,
        "add": cmd_add,
        "seed-from-env": cmd_seed_env,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
