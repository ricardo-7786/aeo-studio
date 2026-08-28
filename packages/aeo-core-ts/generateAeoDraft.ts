import type { Lesson, LessonRecording, Tag, User } from "@shared/schema";
import type { IStorage } from "../storage";
import {
  AeoProfileRequiredError,
  aeoProfileFromEnv,
  resolveLessonAcademyKey,
  rowToAeoAcademyProfile,
} from "./academy";
import { buildAnonymizedLessonSource, pickRecordingsForStt } from "./buildLessonSource";
import {
  articleToMarkdown,
  optimizeLessonToDualChannels,
} from "./optimize";
import { buildJsonLd } from "./schemaLd";
import { transcribeAudioUrl } from "./stt";
import type { AeoDraftResult } from "./types";

export type GenerateAeoDraftOptions = {
  storage: IStorage;
  lesson: Lesson;
  student?: User | null;
  teacher?: User | null;
  tags: Tag[];
  recordings: LessonRecording[];
  weeklyHomework?: string | null;
  /** 중요포인트 녹음 STT 포함 (기본 true) */
  includeStt?: boolean;
  maxSttClips?: number;
};

async function resolveAcademyProfile(storage: IStorage, academyKey: string) {
  const key = academyKey.trim();
  if (!key) throw new AeoProfileRequiredError("");

  let row = await storage.getAcademyAeoProfile(key);
  if (!row) {
    const seed = aeoProfileFromEnv();
    if (seed && seed.academyKey === key) {
      row = await storage.upsertAcademyAeoProfile({ ...seed, updatedByUserId: null });
    }
  }
  if (!row) throw new AeoProfileRequiredError(key);
  return rowToAeoAcademyProfile(row);
}

export async function generateAeoDraftFromLesson(
  opts: GenerateAeoDraftOptions,
): Promise<AeoDraftResult> {
  const includeStt = opts.includeStt !== false;
  const maxStt = opts.maxSttClips ?? 12;
  const academyKey = resolveLessonAcademyKey(opts.teacher, opts.student);
  const academy = await resolveAcademyProfile(opts.storage, academyKey);

  const sttSnippets: AeoDraftResult["sttSnippets"] = [];
  if (includeStt) {
    const clips = pickRecordingsForStt(opts.recordings, maxStt);
    for (const clip of clips) {
      try {
        const text = await transcribeAudioUrl(clip.audioUrl);
        sttSnippets.push({
          recordingId: clip.id,
          title: (clip.title || "").trim() || `녹음 #${clip.id}`,
          text,
        });
      } catch (err) {
        console.warn(
          `[aeo] STT skip recording #${clip.id}:`,
          err instanceof Error ? err.message : err,
        );
      }
    }
  }

  const sourceText = buildAnonymizedLessonSource({
    lesson: opts.lesson,
    student: opts.student,
    teacher: opts.teacher,
    tags: opts.tags,
    recordings: opts.recordings,
    sttSnippets,
    weeklyHomework: opts.weeklyHomework,
  });

  if (!sourceText.replace(/\s+/g, "").length) {
    throw new Error(
      "AEO로 만들 내용이 없습니다. 핵심 코칭 포인트·태그·중요 포인트 녹음 중 하나 이상을 남겨 주세요.",
    );
  }

  const { tistory: article, naver } = await optimizeLessonToDualChannels(sourceText, academy);
  const markdown = articleToMarkdown(article);
  const jsonLd = buildJsonLd(academy, article);
  const generatedAt = new Date().toISOString();

  return {
    article,
    markdown,
    naver,
    jsonLd,
    sourceText,
    sttSnippets,
    generatedAt,
  };
}

export { AeoProfileRequiredError, resolveLessonAcademyKey };
