"""STT 검토 항목 모델 — subject_facts와 stt_music_review 공통."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SttReviewItem:
    severity: str  # info | warn
    category: str  # string_vs_fret | theory_mismatch | homophone | stt_inconsistent
    message: str
    excerpt: str = ""
