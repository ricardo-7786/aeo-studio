"""AEO 템플릿 — SerpAPI/수동 URL → 구조 추출 → 캐시 → 프롬프트."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import Settings, load_settings
from core.template.content_extractor import extract_post_structure
from core.template.models import AeoTemplate, PostStructure
from core.template.prompt_block import format_template_guide
from core.template.serp_fetcher import fetch_top_blog_urls
from core.template.structurer import structure_template
from db.connection import is_db_configured

ROOT = Path(__file__).resolve().parent.parent
FILE_CACHE_DIR = ROOT / ".cache" / "aeo_templates"


def _normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.strip().split())


def _cache_file(keyword: str, channel: str) -> Path:
    digest = hashlib.sha256(f"{channel}:{_normalize_keyword(keyword)}".encode()).hexdigest()[:16]
    return FILE_CACHE_DIR / f"{channel}_{digest}.json"


def _load_file_cache(keyword: str, channel: str, max_age_hours: int) -> AeoTemplate | None:
    path = _cache_file(keyword, channel)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(data["fetched_at"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - fetched > timedelta(hours=max_age_hours):
            return None
        return AeoTemplate.from_cache_dict(data["template"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _save_file_cache(keyword: str, channel: str, template: AeoTemplate, raw: list[dict]) -> None:
    FILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "template": template.to_cache_dict(),
        "raw_extractions": raw,
    }
    _cache_file(keyword, channel).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_manual_urls(raw: str | list[str] | None) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        lines = raw
    else:
        lines = raw.replace(",", "\n").splitlines()
    out: list[str] = []
    for line in lines:
        url = line.strip()
        if url.startswith("http") and url not in out:
            out.append(url)
    return out


def get_or_build_template(
    *,
    target_keyword: str,
    channel: str = "naver",
    manual_urls: str | list[str] | None = None,
    force_refresh: bool = False,
    settings: Settings | None = None,
) -> AeoTemplate:
    cfg = settings or load_settings()
    keyword = _normalize_keyword(target_keyword)
    ch = channel.strip().lower()
    if not keyword:
        raise ValueError("target_keyword를 입력하세요.")

    if not force_refresh:
        cached = _load_cached(keyword, ch, cfg.template_cache_hours)
        if cached:
            return cached

    urls = _parse_manual_urls(manual_urls)
    if not urls:
        urls = fetch_top_blog_urls(
            keyword,
            channel=ch,
            api_key=cfg.serpapi_key,
            limit=3,
        )
    if not urls:
        raise ValueError(
            "참고 URL을 찾지 못했습니다. SerpAPI 키를 확인하거나 수동 URL을 입력하세요."
        )

    posts: list[PostStructure] = []
    errors: list[str] = []
    for url in urls[:3]:
        try:
            posts.append(extract_post_structure(url))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {exc}")

    if not posts:
        raise ValueError("URL에서 본문 구조를 추출하지 못했습니다. " + "; ".join(errors))

    template = structure_template(
        keyword=keyword,
        channel=ch,
        posts=posts,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
    )
    raw = [p.model_dump() for p in posts]
    _save_cached(keyword, ch, template, raw, cfg.template_cache_hours)
    return template


def _load_cached(keyword: str, channel: str, max_age_hours: int) -> AeoTemplate | None:
    if is_db_configured():
        try:
            from db.template_repo import get_cached_template

            row = get_cached_template(keyword, channel, max_age_hours=max_age_hours)
            if row:
                return AeoTemplate.from_cache_dict(row.template_json)
        except Exception:
            pass
    return _load_file_cache(keyword, channel, max_age_hours)


def _save_cached(
    keyword: str,
    channel: str,
    template: AeoTemplate,
    raw: list[dict],
    max_age_hours: int,
) -> None:
    _save_file_cache(keyword, channel, template, raw)
    if is_db_configured():
        try:
            from db.template_repo import upsert_template

            upsert_template(
                keyword=keyword,
                channel=channel,
                source_urls=template.source_urls,
                template_json=template.to_cache_dict(),
                raw_extractions=raw,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ! DB 템플릿 캐시 저장 실패 (파일 캐시는 유지): {exc}")


def resolve_template_guide(
    *,
    use_template: bool,
    target_keyword: str = "",
    template_channel: str = "naver",
    manual_urls: str | list[str] | None = None,
    force_refresh: bool = False,
    settings: Settings | None = None,
) -> tuple[str | None, AeoTemplate | None]:
    if not use_template:
        return None, None
    keyword = _normalize_keyword(target_keyword)
    if not keyword and not _parse_manual_urls(manual_urls):
        raise ValueError("템플릿 사용 시 target_keyword 또는 참고 URL이 필요합니다.")
    if not keyword:
        keyword = "manual-reference"
    template = get_or_build_template(
        target_keyword=keyword,
        channel=template_channel,
        manual_urls=manual_urls,
        force_refresh=force_refresh,
        settings=settings,
    )
    return format_template_guide(template), template
