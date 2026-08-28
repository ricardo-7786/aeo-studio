/**
 * 포인트/레슨 녹음 STT 스모크 테스트.
 *
 * Usage:
 *   OPENAI_API_KEY=sk-... npx tsx scripts/smoke-stt-lesson-recording.ts
 *   OPENAI_API_KEY=sk-... npx tsx scripts/smoke-stt-lesson-recording.ts --file /tmp/coda-stt-samples/juhyeon-pronunciation-25s.mp3
 *   OPENAI_API_KEY=sk-... npx tsx scripts/smoke-stt-lesson-recording.ts --recording-id 1586 --max-seconds 30
 *
 * Loads .env.local automatically.
 */
import { config } from "dotenv";
config({ path: ".env.local" });
config();

import { existsSync, writeFileSync, mkdirSync } from "fs";
import { basename, join } from "path";
import { spawnSync } from "child_process";
import pg from "pg";
import { normalizeDatabaseUrl } from "../server/databaseUrl";

type Args = {
  file?: string;
  recordingId?: number;
  maxSeconds: number;
  language: string;
};

function parseArgs(argv: string[]): Args {
  const out: Args = { maxSeconds: 45, language: "ko" };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--file") out.file = argv[++i];
    else if (a === "--recording-id") out.recordingId = Number(argv[++i]);
    else if (a === "--max-seconds") out.maxSeconds = Number(argv[++i]);
    else if (a === "--language") out.language = argv[++i];
  }
  return out;
}

async function resolveDbAudioUrl(recordingId: number): Promise<{ audioUrl: string; meta: string }> {
  const raw = process.env.DIRECT_URL?.trim() || process.env.DATABASE_URL?.trim() || "";
  const url = normalizeDatabaseUrl(raw);
  if (!url) throw new Error("DATABASE_URL / DIRECT_URL required for --recording-id");
  const pool = new pg.Pool({
    connectionString: url,
    ssl: /supabase|sslmode=require|render\.com/i.test(url) ? { rejectUnauthorized: false } : undefined,
  });
  try {
    const { rows } = await pool.query(
      `SELECT lr.id, lr.audio_url, lr.title AS rec_title, l.title AS lesson_title, u.full_name
       FROM lesson_recordings lr
       JOIN lessons l ON l.id = lr.lesson_id
       JOIN users u ON u.id = l.student_id
       WHERE lr.id = $1`,
      [recordingId],
    );
    const row = rows[0];
    if (!row?.audio_url) throw new Error(`recording ${recordingId} not found`);
    return {
      audioUrl: row.audio_url,
      meta: `${row.full_name} · ${row.lesson_title} · recording #${row.id}`,
    };
  } finally {
    await pool.end();
  }
}

async function downloadToTemp(audioUrl: string): Promise<string> {
  const dir = "/tmp/coda-stt-samples";
  mkdirSync(dir, { recursive: true });
  const name = basename(new URL(audioUrl).pathname) || `rec-${Date.now()}.wav`;
  const path = join(dir, name);
  if (!existsSync(path)) {
    const res = await fetch(audioUrl);
    if (!res.ok) throw new Error(`download failed ${res.status}`);
    writeFileSync(path, Buffer.from(await res.arrayBuffer()));
  }
  return path;
}

function trimWithFfmpeg(inputPath: string, maxSeconds: number): string {
  const out = join("/tmp/coda-stt-samples", `${basename(inputPath, ".wav")}-stt-${maxSeconds}s.mp3`);
  const r = spawnSync(
    "ffmpeg",
    ["-y", "-i", inputPath, "-t", String(maxSeconds), "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-q:a", "4", out],
    { encoding: "utf8" },
  );
  if (r.status !== 0) {
    throw new Error(`ffmpeg failed: ${r.stderr?.slice(-400)}`);
  }
  return out;
}

async function whisperTranscribe(filePath: string, language: string): Promise<{ text: string; raw: unknown }> {
  const key = process.env.OPENAI_API_KEY?.trim();
  if (!key) {
    throw new Error(
      "OPENAI_API_KEY 가 없습니다. 예: OPENAI_API_KEY=sk-... npx tsx scripts/smoke-stt-lesson-recording.ts --file ...",
    );
  }

  const buf = await import("fs/promises").then((fs) => fs.readFile(filePath));
  const form = new FormData();
  form.append("file", new File([buf], basename(filePath), { type: "audio/mpeg" }));
  form.append("model", "whisper-1");
  form.append("language", language);
  form.append("response_format", "verbose_json");
  form.append("timestamp_granularities[]", "segment");

  const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}` },
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`Whisper API ${res.status}: ${JSON.stringify(data)}`);
  }
  return { text: String((data as { text?: string }).text ?? ""), raw: data };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  let filePath = args.file;
  let label = filePath ?? "";

  if (!filePath && args.recordingId) {
    const { audioUrl, meta } = await resolveDbAudioUrl(args.recordingId);
    label = meta;
    const downloaded = await downloadToTemp(audioUrl);
    filePath = trimWithFfmpeg(downloaded, args.maxSeconds);
  }

  if (!filePath) {
    // default: prepared 주현상 samples if present
    const defaults = [
      "/tmp/coda-stt-samples/juhyeon-pronunciation-25s.mp3",
      "/tmp/coda-stt-samples/juhyeon-pop-25s.mp3",
    ].filter((p) => existsSync(p));
    if (defaults.length === 0) {
      console.error("Usage: --file PATH | --recording-id N  (또는 샘플 mp3를 먼저 준비)");
      process.exit(1);
    }
    for (const p of defaults) {
      console.log("\n==========", p, "==========");
      const { text, raw } = await whisperTranscribe(p, args.language);
      const segments = (raw as { segments?: Array<{ start: number; end: number; text: string }> }).segments ?? [];
      console.log("TRANSCRIPT:\n", text.trim() || "(empty)");
      if (segments.length) {
        console.log("\nSEGMENTS:");
        for (const s of segments.slice(0, 12)) {
          console.log(`  [${s.start.toFixed(1)}–${s.end.toFixed(1)}] ${s.text.trim()}`);
        }
      }
    }
    return;
  }

  console.log("input:", label || filePath);
  const { text, raw } = await whisperTranscribe(filePath, args.language);
  const segments = (raw as { segments?: Array<{ start: number; end: number; text: string }> }).segments ?? [];
  console.log("\nTRANSCRIPT:\n", text.trim() || "(empty)");
  if (segments.length) {
    console.log("\nSEGMENTS:");
    for (const s of segments.slice(0, 20)) {
      console.log(`  [${s.start.toFixed(1)}–${s.end.toFixed(1)}] ${s.text.trim()}`);
    }
  }
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
