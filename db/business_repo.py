"""업체(워크스페이스) CRUD — businesses 테이블."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from db.connection import get_connection


@dataclass(frozen=True)
class BusinessRow:
    business_key: str
    industry: str
    name: str
    location: str
    address: str
    phone: str
    url: str
    services: str
    evidence: str
    geo_lat: str | None
    geo_lng: str | None
    price_range: str
    opening_hours: str


def _row_from_record(rec: tuple[Any, ...]) -> BusinessRow:
    return BusinessRow(
        business_key=rec[0],
        industry=rec[1] or "general",
        name=rec[2],
        location=rec[3] or "",
        address=rec[4] or "",
        phone=rec[5] or "",
        url=rec[6] or "",
        services=rec[7] or "",
        evidence=rec[8] or "",
        geo_lat=rec[9],
        geo_lng=rec[10],
        price_range=rec[11] or "$$",
        opening_hours=rec[12] or "",
    )


_SELECT = """
SELECT business_key, industry, name, location, address, phone, url, services, evidence,
       geo_lat, geo_lng, price_range, opening_hours
FROM businesses
"""


class BusinessRepo:
    def get(self, business_key: str) -> BusinessRow | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{_SELECT} WHERE business_key = %s", (business_key.strip(),))
                rec = cur.fetchone()
        return _row_from_record(rec) if rec else None

    def list_all(self, limit: int = 100) -> list[BusinessRow]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"{_SELECT} ORDER BY updated_at DESC NULLS LAST, business_key LIMIT %s",
                    (limit,),
                )
                rows = cur.fetchall()
        return [_row_from_record(r) for r in rows]

    def upsert(self, row: BusinessRow) -> BusinessRow:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO businesses (
                      business_key, industry, name, location, address, phone, url,
                      services, evidence, geo_lat, geo_lng, price_range, opening_hours,
                      updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, CURRENT_TIMESTAMP)
                    ON CONFLICT (business_key) DO UPDATE SET
                      industry = EXCLUDED.industry,
                      name = EXCLUDED.name,
                      location = EXCLUDED.location,
                      address = EXCLUDED.address,
                      phone = EXCLUDED.phone,
                      url = EXCLUDED.url,
                      services = EXCLUDED.services,
                      evidence = EXCLUDED.evidence,
                      geo_lat = EXCLUDED.geo_lat,
                      geo_lng = EXCLUDED.geo_lng,
                      price_range = EXCLUDED.price_range,
                      opening_hours = EXCLUDED.opening_hours,
                      updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        row.business_key.strip(),
                        row.industry or "general",
                        row.name.strip(),
                        row.location,
                        row.address,
                        row.phone,
                        row.url,
                        row.services,
                        row.evidence,
                        row.geo_lat,
                        row.geo_lng,
                        row.price_range or "$$",
                        row.opening_hours,
                    ),
                )
            conn.commit()
        saved = self.get(row.business_key)
        if not saved:
            raise RuntimeError("업체 저장 후 조회에 실패했습니다.")
        return saved
