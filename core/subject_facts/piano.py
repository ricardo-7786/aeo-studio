"""피아노 STT 검증 — 건반·반음 위치 등."""

from __future__ import annotations

import re

from core.stt_review_models import SttReviewItem


def audit_piano_stt(text: str) -> list[SttReviewItem]:
    items: list[SttReviewItem] = []
    if not text.strip():
        return items

    # 흑건반 개수 등 자주 틀리는 서술
    if re.search(r"흑건반\s*(\d+)\s*개", text):
        m = re.search(r"흑건반\s*(\d+)\s*개", text)
        if m and m.group(1) not in ("5", "12"):
            items.append(
                SttReviewItem(
                    severity="warn",
                    category="theory_mismatch",
                    message=f"STT: 옥타브당 흑건반 {m.group(1)}개. 일반적으로 5개입니다. 녹음 확인.",
                    excerpt=m.group(0),
                )
            )

    if re.search(r"건반\s*(\d+)\s*개", text):
        m = re.search(r"건반\s*(\d+)\s*개", text)
        if m and m.group(1) not in ("88",):
            items.append(
                SttReviewItem(
                    severity="info",
                    category="theory_mismatch",
                    message=f"STT: 건반 {m.group(1)}개. 일반 피아노는 88건반입니다. 맥락 확인.",
                    excerpt=m.group(0),
                )
            )

    return items
