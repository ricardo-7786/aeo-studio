"""기타 표준 이론 — STT 오인식 감지용 (자동 수정 아님)."""

from __future__ import annotations

import re

from core.stt_review_models import SttReviewItem

# 표준 튜닝 (6→1). 교육용 참고값 — 비표준 튜닝 레슨일 수 있어 경고만 표시.
STANDARD_TUNING: dict[int, str] = {6: "E", 5: "A", 4: "D", 3: "G", 2: "B", 1: "E"}

_NOTE_MAP: dict[str, str] = {
    "e": "E",
    "이": "E",
    "a": "A",
    "에이": "A",
    "d": "D",
    "디": "D",
    "g": "G",
    "지": "G",
    "b": "B",
    "비": "B",
    "c": "C",
    "씨": "C",
    "f": "F",
    "에프": "F",
}


def _normalize_note(raw: str) -> str | None:
    s = (raw or "").strip().upper().replace("♯", "#").replace("♭", "b")
    if not s:
        return None
    low = s.lower()
    if low in _NOTE_MAP:
        return _NOTE_MAP[low]
    if re.match(r"^[A-G][#B]?$", s, re.I):
        return s[0].upper() + (s[1:] if len(s) > 1 else "")
    return None


def _extract_string_note(segment: str) -> str | None:
    """「N번 줄 … X음」 구간에서 음 이름 추출."""
    m = re.search(
        r"(?:은|는|이|가)?\s*"
        r"([A-Ga-g이에이디지비씨에프파솔라시도][#b♭♯샵플랫]?|E|F|G|A|B|C|D)"
        r"(?:음|으로|로)?",
        segment,
    )
    if not m:
        return None
    return _normalize_note(m.group(1))


def audit_guitar_stt(text: str) -> list[SttReviewItem]:
    items: list[SttReviewItem] = []
    if not text.strip():
        return items

    # 줄 vs 플랫 혼동 (대표: 1번 줄 E vs 1번 플랫 C)
    if re.search(r"1번\s*플랫", text) and re.search(r"1번\s*줄", text):
        items.append(
            SttReviewItem(
                severity="warn",
                category="string_vs_fret",
                message=(
                    "「1번 플랫」(프렛 위치)과「1번 줄」(현)이 모두 등장합니다. "
                    "Whisper가 줄/프렛을 섞었을 수 있으니 녹음을 확인하세요."
                ),
                excerpt=_excerpt(text, "1번"),
            )
        )

    for num in range(1, 7):
        if re.search(rf"{num}번\s*플랫", text) and re.search(rf"{num}번\s*줄", text):
            if num == 1:
                continue  # already covered
            items.append(
                SttReviewItem(
                    severity="info",
                    category="string_vs_fret",
                    message=f"「{num}번 플랫」과「{num}번 줄」이 함께 나옵니다. 프렛 번호와 현 번호를 구분해 확인하세요.",
                    excerpt=_excerpt(text, f"{num}번"),
                )
            )

    # 줄별 음 주장 추출
    claims: dict[int, set[str]] = {}
    for m in re.finditer(r"(\d)\s*번\s*줄[^.\n]{0,60}", text):
        string_num = int(m.group(1))
        note = _extract_string_note(m.group(0))
        if note:
            claims.setdefault(string_num, set()).add(note)

    for string_num, notes in claims.items():
        if len(notes) > 1:
            items.append(
                SttReviewItem(
                    severity="warn",
                    category="stt_inconsistent",
                    message=(
                        f"STT에서 {string_num}번 줄 음이 {', '.join(sorted(notes))}로 "
                        "서로 다르게 적혔습니다. 오인식 가능성이 큽니다."
                    ),
                    excerpt=_excerpt(text, f"{string_num}번 줄"),
                )
            )
            continue
        note = next(iter(notes))
        expected = STANDARD_TUNING.get(string_num)
        if expected and note != expected:
            items.append(
                SttReviewItem(
                    severity="warn",
                    category="theory_mismatch",
                    message=(
                        f"STT: {string_num}번 줄 = {note}음. "
                        f"표준 튜닝은 {expected}입니다. "
                        "녹음이 맞는지 확인하세요(비표준 튜닝·오인식 모두 가능)."
                    ),
                    excerpt=_excerpt(text, f"{string_num}번 줄"),
                )
            )

    # 동음이의어: 이음/E, 비음/B 등
    if re.search(r"이음|이\s*으로\s*시작", text) and "E" not in text.upper():
        items.append(
            SttReviewItem(
                severity="info",
                category="homophone",
                message="「이음」은 E음 오인식일 수 있습니다. 원문 음성에서 E인지 확인하세요.",
                excerpt=_excerpt(text, "이음"),
            )
        )

    return items


def _excerpt(text: str, needle: str, radius: int = 50) -> str:
    idx = text.find(needle)
    if idx < 0:
        return ""
    start = max(0, idx - radius)
    end = min(len(text), idx + len(needle) + radius)
    return text[start:end].strip()
