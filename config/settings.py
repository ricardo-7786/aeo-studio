"""애플리케이션 설정 — `.env` + DB 업체 프로필."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv

from config.industry import normalize_industry

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class BusinessProfile:
    """업체(브랜드) 정보 — AEO 본문·JSON-LD에 단일 명칭으로 유지."""

    business_key: str
    industry: str
    name: str
    location: str
    address: str
    phone: str
    url: str
    services: list[str]
    evidence: str
    geo_lat: float | None
    geo_lng: float | None
    price_range: str
    opening_hours: str
    adjacent_areas: list[str] = field(default_factory=list)


# 하위 호환 alias
AcademyProfile = BusinessProfile


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    whisper_model: str
    whisper_language: str
    business: BusinessProfile
    publish_platform: str
    dry_run: bool
    output_dir: Path
    database_url: str
    default_business_key: str

    # WordPress
    wp_site_url: str
    wp_username: str
    wp_app_password: str
    wp_status: str
    wp_categories: list[int] = field(default_factory=list)
    wp_tags: list[int] = field(default_factory=list)

    # Tistory
    tistory_access_token: str = ""
    tistory_blog_name: str = ""
    tistory_visibility: int = 3

    # SerpAPI / 템플릿 캐시
    serpapi_key: str = ""
    template_cache_hours: int = 72

    @property
    def academy(self) -> BusinessProfile:
        """하위 호환 — settings.academy → settings.business."""
        return self.business


def _parse_int_list(raw: str) -> list[int]:
    if not raw.strip():
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


def _profile_from_env() -> BusinessProfile:
    services = [
        s.strip()
        for s in _env("ACADEMY_SERVICES", _env("BUSINESS_SERVICES", "보컬, 기타")).split(",")
        if s.strip()
    ]
    lat_raw = _env("ACADEMY_GEO_LAT", _env("BUSINESS_GEO_LAT"))
    lng_raw = _env("ACADEMY_GEO_LNG", _env("BUSINESS_GEO_LNG"))
    name = _env("BUSINESS_NAME", _env("ACADEMY_NAME", "로컬 비즈니스"))
    key = _env("BUSINESS_KEY", _env("ACADEMY_NAME", name))

    default_industry = (
        "education"
        if _env("ACADEMY_NAME") or _env("ACADEMY_EVIDENCE")
        else "general"
    )
    return BusinessProfile(
        business_key=key,
        industry=normalize_industry(
            _env("BUSINESS_INDUSTRY", _env("INDUSTRY", default_industry)),
        ),
        name=name,
        location=_env("BUSINESS_LOCATION", _env("ACADEMY_LOCATION", "")),
        address=_env("BUSINESS_ADDRESS", _env("ACADEMY_ADDRESS", "")),
        phone=_env("BUSINESS_PHONE", _env("ACADEMY_PHONE", "")),
        url=_env("BUSINESS_URL", _env("ACADEMY_URL", "")),
        services=services,
        evidence=_env("BUSINESS_EVIDENCE", _env("ACADEMY_EVIDENCE", "")),
        geo_lat=float(lat_raw) if lat_raw else None,
        geo_lng=float(lng_raw) if lng_raw else None,
        price_range=_env("BUSINESS_PRICE_RANGE", _env("ACADEMY_PRICE_RANGE", "$$")),
        opening_hours=_env(
            "BUSINESS_OPENING_HOURS",
            _env("ACADEMY_OPENING_HOURS", "Mo-Sa 10:00-22:00"),
        ),
        adjacent_areas=[
            s.strip()
            for s in _env("BUSINESS_ADJACENT_AREAS", _env("ACADEMY_ADJACENT_AREAS", "")).split(",")
            if s.strip()
        ],
    )


def _row_to_profile(row) -> BusinessProfile:
    services = [s.strip() for s in (row.services or "").split(",") if s.strip()]
    lat = float(row.geo_lat) if row.geo_lat else None
    lng = float(row.geo_lng) if row.geo_lng else None
    return BusinessProfile(
        business_key=row.business_key,
        industry=normalize_industry(row.industry),
        name=row.name,
        location=row.location,
        address=row.address,
        phone=row.phone,
        url=row.url,
        services=services,
        evidence=row.evidence,
        geo_lat=lat,
        geo_lng=lng,
        price_range=row.price_range,
        opening_hours=row.opening_hours,
        adjacent_areas=[s.strip() for s in (row.adjacent_areas or "").split(",") if s.strip()],
    )


def load_business_profile(
    *,
    business_key: str | None = None,
    industry_override: str | None = None,
) -> BusinessProfile:
    """DB 우선 → .env 폴백."""
    key = (business_key or _env("DEFAULT_BUSINESS_KEY", _env("BUSINESS_KEY", ""))).strip()

    if key:
        try:
            from db.business_repo import BusinessRepo
            from db.connection import is_db_configured

            if is_db_configured():
                row = BusinessRepo().get(key)
                if row:
                    profile = _row_to_profile(row)
                    if industry_override:
                        return replace(profile, industry=normalize_industry(industry_override))
                    return profile
        except Exception as exc:  # noqa: BLE001 — DB 없으면 env 폴백
            print(f"  ! DB 프로필 로드 실패, .env 사용: {exc}")

    profile = _profile_from_env()
    if business_key:
        profile = replace(profile, business_key=business_key.strip())
    if industry_override:
        profile = replace(profile, industry=normalize_industry(industry_override))
    return profile


def load_settings(
    *,
    business_key: str | None = None,
    industry_override: str | None = None,
) -> Settings:
    business = load_business_profile(
        business_key=business_key,
        industry_override=industry_override,
    )

    return Settings(
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_model=_env("OPENAI_MODEL", "gpt-4o-mini"),
        whisper_model=_env("WHISPER_MODEL", "whisper-1"),
        whisper_language=_env("WHISPER_LANGUAGE", "ko"),
        business=business,
        publish_platform=_env("PUBLISH_PLATFORM", "wordpress").lower(),
        dry_run=_env_bool("DRY_RUN", False),
        output_dir=Path(_env("OUTPUT_DIR", str(ROOT_DIR / "output"))),
        database_url=_env("DIRECT_URL", _env("DATABASE_URL")),
        default_business_key=_env("DEFAULT_BUSINESS_KEY", business.business_key),
        wp_site_url=_env("WP_SITE_URL").rstrip("/"),
        wp_username=_env("WP_USERNAME"),
        wp_app_password=_env("WP_APP_PASSWORD"),
        wp_status=_env("WP_STATUS", "publish"),
        wp_categories=_parse_int_list(_env("WP_CATEGORIES")),
        wp_tags=_parse_int_list(_env("WP_TAGS")),
        tistory_access_token=_env("TISTORY_ACCESS_TOKEN"),
        tistory_blog_name=_env("TISTORY_BLOG_NAME"),
        tistory_visibility=int(_env("TISTORY_VISIBILITY", "3") or "3"),
        serpapi_key=_env("SERPAPI_KEY"),
        template_cache_hours=int(_env("TEMPLATE_CACHE_HOURS", "72") or "72"),
    )
