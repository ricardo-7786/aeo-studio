"""Schema.org JSON-LD (LocalBusiness + EducationalOrganization) 생성."""

from __future__ import annotations

import json
from typing import Any

from config.settings import AcademyProfile
from core.aeo_optimizer import AEOArticle, faq_qa
from config.industry import INDUSTRY_META, normalize_industry


def _org_types(industry: str) -> list[str]:
    meta = INDUSTRY_META[normalize_industry(industry)]
    hint = meta["schema_hint"]
    if hint == "LocalBusiness":
        return ["LocalBusiness"]
    return ["LocalBusiness", hint]


def build_json_ld(
    academy: AcademyProfile,
    article: AEOArticle | None = None,
) -> dict[str, Any]:
    """LocalBusiness + 업종 Schema + BlogPosting/FAQPage."""

    industry = normalize_industry(getattr(academy, "industry", "education"))
    org: dict[str, Any] = {
        "@type": _org_types(industry),
        "@id": f"{academy.url.rstrip('/')}/#organization" if academy.url else "#organization",
        "name": academy.name,
        "description": (
            f"{academy.location} {academy.name}. "
            f"주요 과정: {', '.join(academy.services)}. "
            f"{academy.evidence}".strip()
        ).strip(),
        "url": academy.url or None,
        "telephone": academy.phone or None,
        "priceRange": academy.price_range or None,
        "openingHours": academy.opening_hours or None,
        "areaServed": academy.location or None,
        "knowsAbout": academy.services,
    }

    if academy.address:
        org["address"] = {
            "@type": "PostalAddress",
            "streetAddress": academy.address,
            "addressLocality": _guess_locality(academy.address),
            "addressRegion": _guess_region(academy.address),
            "addressCountry": "KR",
        }

    if academy.geo_lat is not None and academy.geo_lng is not None:
        org["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": academy.geo_lat,
            "longitude": academy.geo_lng,
        }

    # None 값 제거
    org = {k: v for k, v in org.items() if v is not None}

    graph: list[dict[str, Any]] = [org]

    if article:
        article_node: dict[str, Any] = {
            "@type": "BlogPosting",
            "headline": article.title,
            "description": article.meta_description,
            "articleBody": article.one_sentence_answer,
            "keywords": ", ".join(article.keywords) if article.keywords else None,
            "inLanguage": "ko-KR",
            "author": {"@id": org["@id"]},
            "publisher": {"@id": org["@id"]},
            "about": {"@id": org["@id"]},
        }
        article_node = {k: v for k, v in article_node.items() if v is not None}
        graph.append(article_node)

        if article.faq:
            faq_entities = []
            for item in article.faq:
                q, a = faq_qa(item)
                if not q or not a:
                    continue
                faq_entities.append(
                    {
                        "@type": "Question",
                        "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a},
                    }
                )
            if faq_entities:
                graph.append({"@type": "FAQPage", "mainEntity": faq_entities})

    return {
        "@context": "https://schema.org",
        "@graph": graph,
    }


def json_ld_script_tag(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    return (
        '<script type="application/ld+json">\n'
        f"{serialized}\n"
        "</script>"
    )


def _guess_locality(address: str) -> str:
    # "서울특별시 마포구 ..." → 마포구
    parts = address.split()
    for p in parts:
        if p.endswith(("구", "시", "군")) and p not in {"서울특별시", "부산광역시"}:
            if len(p) <= 4 or p.endswith("구"):
                return p
    return parts[1] if len(parts) > 1 else address


def _guess_region(address: str) -> str:
    parts = address.split()
    return parts[0] if parts else "서울특별시"
