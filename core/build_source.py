"""레슨·STT → 익명화 sourceText — CODA buildLessonSource.ts 포팅."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SttSnippet:
    recording_id: int | str
    title: str
    text: str


@dataclass
class LessonSourceInput:
    lesson_title: str
    teacher_name: str = ""
    academy_name: str = ""
    key_coaching_points: str = ""
    tags: list[tuple[int, str, str]] = field(default_factory=list)  # sec, type, note
    stt_snippets: list[SttSnippet] = field(default_factory=list)
    weekly_homework: str = ""
    summary: str = ""
    student_real_name: str = ""


def anonymize(text: str, real_name: str) -> str:
    if real_name and len(real_name.strip()) >= 2:
        return text.replace(real_name.strip(), "수강생")
    return text


def build_anonymized_lesson_source(inp: LessonSourceInput) -> str:
    real_name = inp.student_real_name.strip()
    lines: list[str] = []

    lines.append(f"레슨 제목: {anonymize(inp.lesson_title, real_name)}")
    lines.append("수강생: 수강생 (실명 비공개)")
    if inp.teacher_name:
        lines.append(f"담당: {inp.teacher_name}")
    if inp.academy_name:
        lines.append(f"학원: {inp.academy_name}")
    lines.append("")

    if inp.key_coaching_points.strip():
        lines.append("[오늘의 핵심 코칭 포인트]")
        lines.append(anonymize(inp.key_coaching_points.strip(), real_name))
        lines.append("")

    if inp.tags:
        lines.append("[중요 레슨 포인트 태그]")
        for sec, tag_type, note in inp.tags:
            note_part = f" {anonymize(note, real_name)}" if note.strip() else ""
            lines.append(f"- ({sec}초 / {tag_type}){note_part}")
        lines.append("")

    if inp.stt_snippets:
        n = len(inp.stt_snippets)
        lines.append(
            f"[중요 포인트 녹음 STT — 같은 날·같은 레슨의 포인트 녹음 {n}개. "
            "하나의 블로그 글에 모두 녹여 쓸 것]"
        )
        for i, s in enumerate(inp.stt_snippets, start=1):
            title = s.title.strip() or f"녹음 #{s.recording_id}"
            lines.append(f"### 포인트 {i}: {title}")
            lines.append(anonymize(s.text.strip(), real_name))
            lines.append("")

    if inp.weekly_homework.strip():
        lines.append("[이번 주 과제]")
        lines.append(anonymize(inp.weekly_homework.strip(), real_name))
        lines.append("")

    if inp.summary.strip() and "AI 요약 기능은 제공되지 않습니다" not in inp.summary:
        lines.append("[요약]")
        lines.append(anonymize(inp.summary.strip(), real_name))

    return "\n".join(lines).strip()


def build_source_from_stt_only(
    *,
    lesson_title: str,
    stt_snippets: list[SttSnippet],
    key_coaching_points: str = "",
    teacher_name: str = "",
    academy_name: str = "",
) -> str:
    """AEO 앱 단독: 여러 포인트 녹음 STT만으로 sourceText 구성."""
    return build_anonymized_lesson_source(
        LessonSourceInput(
            lesson_title=lesson_title,
            teacher_name=teacher_name,
            academy_name=academy_name,
            key_coaching_points=key_coaching_points,
            stt_snippets=stt_snippets,
        )
    )
