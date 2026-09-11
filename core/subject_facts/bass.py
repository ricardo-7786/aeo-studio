"""베이스 STT 검증 — 4현 표준 E-A-D-G (6→3번 줄 표기 관습에 맞춤)."""

from __future__ import annotations

import re

from core.stt_review_models import SttReviewItem

# 많은 강의에서 기타와 같이 4번=저음 E … 1번=G 로 부름
STANDARD_4_STRING: dict[int, str] = {4: "E", 3: "A", 2: "D", 1: "G"}


def audit_bass_stt(text: str) -> list[SttReviewItem]:
    items: list[SttReviewItem] = []
    if not text.strip():
        return items

    if re.search(r"\d번\s*플랫", text) and re.search(r"\d번\s*줄", text):
        items.append(
            SttReviewItem(
                severity="info",
                category="string_vs_fret",
                message="베이스 STT에 「N번 플랫」과「N번 줄」이 함께 있습니다. 프렛·현 번호 혼동 여부를 확인하세요.",
                excerpt=text[:120],
            )
        )

    for m in re.finditer(r"(\d)\s*번\s*줄[^.\n]{0,50}", text):
        num = int(m.group(1))
        seg = m.group(0)
        note_m = re.search(r"([A-G])[#b]?(?:음|으로|로)?", seg, re.I)
        if not note_m or num not in STANDARD_4_STRING:
            continue
        note = note_m.group(1).upper()
        expected = STANDARD_4_STRING[num]
        if note != expected:
            items.append(
                SttReviewItem(
                    severity="warn",
                    category="theory_mismatch",
                    message=(
                        f"STT: {num}번 줄 = {note}. 표준 4현 베이스는 {expected}입니다. "
                        "녹음·오인식 여부를 확인하세요."
                    ),
                    excerpt=seg.strip(),
                )
            )

    return items
