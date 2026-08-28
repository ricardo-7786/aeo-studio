import type { Lesson, LessonRecording, Tag, User } from "@shared/schema";

export type LessonAeoSourceInput = {
  lesson: Lesson;
  student: User | null | undefined;
  teacher: User | null | undefined;
  tags: Tag[];
  recordings: LessonRecording[];
  sttSnippets: { recordingId: number; title: string; text: string }[];
  weeklyHomework?: string | null;
};

/** 학생 실명 제거 + 레슨 구조화 텍스트 */
export function buildAnonymizedLessonSource(input: LessonAeoSourceInput): string {
  const { lesson, student, teacher, tags, sttSnippets, weeklyHomework } = input;
  const realName = student?.fullName?.trim();
  const anonymize = (text: string) => {
    let out = text;
    if (realName && realName.length >= 2) {
      out = out.split(realName).join("수강생");
    }
    return out;
  };

  const lines: string[] = [];
  lines.push(`레슨 제목: ${anonymize(lesson.title)}`);
  lines.push(`수강생: 수강생 (실명 비공개)`);
  if (teacher?.fullName) lines.push(`담당: ${teacher.fullName}`);
  if (teacher?.academyName) lines.push(`학원: ${teacher.academyName}`);
  lines.push("");

  if (lesson.keyCoachingPoints?.trim()) {
    lines.push("[오늘의 핵심 코칭 포인트]");
    lines.push(anonymize(lesson.keyCoachingPoints.trim()));
    lines.push("");
  }

  if (tags.length) {
    lines.push("[중요 레슨 포인트 태그]");
    for (const t of tags) {
      const note = t.note?.trim() ? anonymize(t.note.trim()) : "";
      const sec = Math.round((t.timestampMs || 0) / 1000);
      lines.push(`- (${sec}초 / ${t.type})${note ? ` ${note}` : ""}`);
    }
    lines.push("");
  }

  if (sttSnippets.length) {
    lines.push(
      `[중요 포인트 녹음 STT — 같은 날·같은 레슨의 포인트 녹음 ${sttSnippets.length}개. 하나의 블로그 글에 모두 녹여 쓸 것]`,
    );
    sttSnippets.forEach((s, i) => {
      lines.push(`### 포인트 ${i + 1}: ${s.title || `녹음 #${s.recordingId}`}`);
      lines.push(anonymize(s.text));
      lines.push("");
    });
  }

  if (weeklyHomework?.trim()) {
    lines.push("[이번 주 과제]");
    lines.push(anonymize(weeklyHomework.trim()));
    lines.push("");
  }

  if (lesson.summary?.trim() && !lesson.summary.includes("AI 요약 기능은 제공되지 않습니다")) {
    lines.push("[요약]");
    lines.push(anonymize(lesson.summary.trim()));
  }

  return lines.join("\n").trim();
}

/** STT할 클립 선정: ready + URL, 제목 있는 클립 우선, 레슨 진행 순(오래된→최신), 최대 N개 */
export function pickRecordingsForStt(
  recordings: LessonRecording[],
  max = 12,
): LessonRecording[] {
  const ready = recordings.filter((r) => {
    const status = (r.processingStatus || "ready").toLowerCase();
    return !!r.audioUrl && (status === "ready" || status === "");
  });
  const withTitle = ready.filter((r) => (r.title || "").trim().length > 0);
  const pool = (withTitle.length ? withTitle : ready).slice();
  // 레슨 일지 흐름: 먼저 녹음한 포인트부터
  pool.sort((a, b) => {
    const ta = a.createdAt ? new Date(a.createdAt).getTime() : 0;
    const tb = b.createdAt ? new Date(b.createdAt).getTime() : 0;
    return ta - tb;
  });
  return pool.slice(0, Math.max(0, max));
}
