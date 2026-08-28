/**
 * 레슨 녹음(중요 포인트 클립) → Whisper STT
 * smoke-stt-lesson-recording.ts 와 동일 API, 서버용 단순화 버전
 */

const WHISPER_MODEL = () => (process.env.WHISPER_MODEL || "whisper-1").trim();
const WHISPER_LANGUAGE = () => (process.env.WHISPER_LANGUAGE || "ko").trim();

export async function transcribeAudioUrl(
  audioUrl: string,
  opts?: { maxSeconds?: number },
): Promise<string> {
  const key = process.env.OPENAI_API_KEY?.trim();
  if (!key) throw new Error("OPENAI_API_KEY가 필요합니다 (STT).");

  const res = await fetch(audioUrl);
  if (!res.ok) throw new Error(`오디오 다운로드 실패 HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length > 24 * 1024 * 1024) {
    throw new Error("오디오가 너무 큽니다 (25MB 제한). 짧은 포인트 녹음을 사용하세요.");
  }

  const pathname = (() => {
    try {
      return new URL(audioUrl).pathname;
    } catch {
      return "/clip.webm";
    }
  })();
  const ext = pathname.includes(".") ? pathname.split(".").pop() || "webm" : "webm";
  const filename = `lesson-clip.${ext}`;

  const form = new FormData();
  const mime =
    ext === "mp3" || ext === "mpeg"
      ? "audio/mpeg"
      : ext === "m4a"
        ? "audio/mp4"
        : ext === "wav"
          ? "audio/wav"
          : "audio/webm";
  form.append("file", new File([buf], filename, { type: mime }));
  form.append("model", WHISPER_MODEL());
  form.append("language", WHISPER_LANGUAGE());
  form.append("response_format", "text");

  const sttRes = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}` },
    body: form,
  });
  if (!sttRes.ok) {
    const errText = await sttRes.text().catch(() => "");
    throw new Error(`Whisper STT 실패 HTTP ${sttRes.status}: ${errText.slice(0, 200)}`);
  }
  const text = (await sttRes.text()).trim();
  if (!text) throw new Error("STT 결과가 비어 있습니다.");
  return text;
}
