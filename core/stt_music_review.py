"""STT 음악 이론 과목 — Whisper 보조·정규화·오인식 감지."""

from __future__ import annotations

import re

from core.build_source import SttSnippet
from core.stt_review_models import SttReviewItem
from core.subject_facts import STRICT_THEORY_SUBJECTS
from core.subject_facts.bass import audit_bass_stt
from core.subject_facts.guitar import audit_guitar_stt
from core.subject_facts.piano import audit_piano_stt

__all__ = [
    "SttReviewItem",
    "resolve_whisper_prompt",
    "normalize_music_stt_text",
    "audit_stt_text",
    "process_music_stt_snippets",
    "format_stt_review_block",
    "prepare_theory_stt_snippets",
]

# Whisper initial prompt — 한국어 음악 용어 인식률 향상 (녹음 지식은 맞고 STT만 틀리는 경우 완화)
WHISPER_PROMPTS: dict[str, str] = {
    "기타": (
        "기타 레슨. 튜닝, 프렛, 코드, CAGED, 카포, 스트로킹, "
        "6번 줄 E, 5번 줄 A, 4번 줄 D, 3번 줄 G, 2번 줄 B, 1번 줄 E, "
        "반음, 온음, 옥타브, 12프렛, 플랫, 샵, E코드, C코드, G코드"
    ),
    "베이스": (
        "베이스 레슨. 4번 줄 E, 3번 줄 A, 2번 줄 D, 1번 줄 G, "
        "프렛, 그루브, 슬랩, 반음, 온음"
    ),
    "피아노": (
        "피아노 레슨. 건반, 옥타브, 반음, 온음, 흑건반, 백건반, "
        "도레미파솔라시, 스케일, 화음"
    ),
}

_COMBINED_MUSIC_PROMPT = (
    "음악 레슨. 기타, 베이스, 피아노. 튜닝, 프렛, 코드, 건반, 반음, 온음, CAGED, 카포"
)

# STT 텍스트만 안전하게 고침 (의미 변경 위험 낮은 표기)
_TEXT_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"케이지드|케이지(?=\s*시스템)?", re.I), "CAGED"),
    (re.compile(r"에프\s*샵|F\s*샵", re.I), "F#"),
    (re.compile(r"디\s*샵|D\s*샵", re.I), "D#"),
    (re.compile(r"(\d)\s*프렛"), r"\1프렛"),
    (re.compile(r"(\d)\s*번\s*플랫"), r"\1번 플랫"),
    (re.compile(r"(\d)\s*번\s*줄"), r"\1번 줄"),
]


def resolve_whisper_prompt(
    subject: str,
    *,
    academy_services: list[str] | None = None,
) -> str | None:
    """과목·학원 서비스에 맞는 Whisper hint. 없으면 None."""
    if subject in WHISPER_PROMPTS:
        return WHISPER_PROMPTS[subject]
    services = academy_services or []
    for svc in services:
        if svc in WHISPER_PROMPTS:
            return WHISPER_PROMPTS[svc]
    if STRICT_THEORY_SUBJECTS.intersection(services):
        return _COMBINED_MUSIC_PROMPT
    return None


def normalize_music_stt_text(text: str, subject: str) -> str:
    """Whisper 산출 텍스트 표기만 정리. 음 이름·이론 내용은 바꾸지 않음."""
    if subject not in STRICT_THEORY_SUBJECTS:
        return text
    out = text
    for pattern, repl in _TEXT_REPLACEMENTS:
        out = pattern.sub(repl, out)
    return out


def audit_stt_text(subject: str, text: str) -> list[SttReviewItem]:
    if subject not in STRICT_THEORY_SUBJECTS:
        return []
    auditors = {
        "기타": audit_guitar_stt,
        "베이스": audit_bass_stt,
        "피아노": audit_piano_stt,
    }
    fn = auditors.get(subject)
    return fn(text) if fn else []


def process_music_stt_snippets(
    snippets: list[SttSnippet],
    subject: str,
) -> tuple[list[SttSnippet], list[SttReviewItem]]:
    """정규화 + 과목별 STT 감사. 자동 수정(이론 덮어쓰기)은 하지 않음."""
    if subject not in STRICT_THEORY_SUBJECTS:
        return snippets, []

    all_reviews: list[SttReviewItem] = []
    processed: list[SttSnippet] = []

    for s in snippets:
        normalized = normalize_music_stt_text(s.text, subject)
        reviews = audit_stt_text(subject, normalized)
        all_reviews.extend(reviews)
        processed.append(
            SttSnippet(
                recording_id=s.recording_id,
                title=s.title,
                text=normalized,
            )
        )

    # 중복 메시지 제거
    seen: set[str] = set()
    unique: list[SttReviewItem] = []
    for r in all_reviews:
        key = f"{r.category}:{r.message}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    return processed, unique


def format_stt_review_block(reviews: list[SttReviewItem]) -> str:
    """생성 프롬프트·source_text에 넣을 STT 검토 블록."""
    if not reviews:
        return ""
    lines = [
        "[STT 검토 — Whisper 음성인식 오류 가능. 아래는 녹음 확인 전 단정 서술·FAQ 금지]",
    ]
    for r in reviews:
        prefix = "⚠" if r.severity == "warn" else "·"
        lines.append(f"{prefix} {r.message}")
        if r.excerpt:
            lines.append(f"   원문 근처: …{r.excerpt}…")
    lines.append(
        "위 항목은 STT가 틀렸을 수 있습니다. 확실하지 않은 음·줄·프렛은 본문에 쓰지 말거나 "
        "「녹음 기준으로는 ~」처럼 단정을 피하세요. 표준 이론으로 STT를 덮어쓰지 마세요."
    )
    return "\n".join(lines)


def prepare_theory_stt_snippets(
    snippets: list[SttSnippet],
    *,
    subject: str,
    lesson_title: str = "",
    target_keyword: str = "",
    academy_profile=None,
) -> tuple[list[SttSnippet], list[SttReviewItem], str]:
    """STT 정규화·감사. (snippets, reviews, review_block) 반환."""
    from core.lesson_subject import detect_lesson_subject

    processed, reviews = process_music_stt_snippets(snippets, subject)

    if academy_profile is not None:
        combined = "\n".join(s.text for s in processed)
        refined = detect_lesson_subject(
            academy_profile,
            source_text=combined,
            lesson_title=lesson_title,
            target_keyword=target_keyword,
        )
        if refined != subject and refined in STRICT_THEORY_SUBJECTS:
            processed, more = process_music_stt_snippets(processed, refined)
            seen = {f"{r.category}:{r.message}" for r in reviews}
            for r in more:
                key = f"{r.category}:{r.message}"
                if key not in seen:
                    reviews.append(r)
                    seen.add(key)

    return processed, reviews, format_stt_review_block(reviews)
