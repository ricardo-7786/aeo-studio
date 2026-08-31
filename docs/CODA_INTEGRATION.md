# CODA ↔ 학원홍보 AEO 연동

## 역할 분담

| | CODA (Vocal-Coach) | 학원홍보 AEO |
|---|---|---|
| 레슨 녹음 | ✅ (학생·강사용) | URL/STT 수신 |
| STT | (선택) CODA에서 미리 | ✅ Whisper (`transcribe_audio_url`) |
| AEO/SEO 초안 | API 호출 | ✅ (메인) |
| 발행·순위 추적 | ❌ | ✅ |

---

## 1) 웹 UI (`/generate`)

**CODA 레슨 녹음 연동** 패널:

| 입력 | 설명 |
|------|------|
| **CODA 레슨 선택** | `CODA_DATABASE_URL` 설정 시 DB에서 레슨·녹음 자동 로드 (우선) |
| CODA 녹음 URL | `포인트 제목\|https://...` 한 줄에 하나 |
| CODA JSON | 레슨 전체 payload (recordings, tags, sttSnippets 등) |
| 현장 메모 | `keyCoachingPoints` 보조 |

**`.env` (CODA DB 자동 불러오기):**

```bash
# CODA Supabase Postgres — AEO DATABASE_URL과 별도
CODA_DATABASE_URL=postgresql://postgres:...@db....supabase.co:5432/postgres
CODA_TEACHER_NAME=전창영
```

CODA 프로젝트 `.env.local`의 `DATABASE_URL` 또는 `DIRECT_URL` 값을 그대로 복사하면 됩니다.

서버: `python -m web.app` → http://127.0.0.1:8787/generate

---

## 2) HTTP API (CODA 앱에서 호출)

### 레슨 목록·상세 (CODA DB)

```http
GET /api/v1/coda/lessons?teacher=전창영&limit=40
GET /api/v1/coda/lessons/{lessonId}
Authorization: Bearer <AEO_API_KEY>   # .env AEO_API_KEY 설정 시
```

### 초안 생성

```http
POST /api/v1/drafts/generate
Authorization: Bearer <AEO_API_KEY>   # .env AEO_API_KEY 설정 시
Content-Type: application/json
```

**방법 A — CODA DB 레슨 ID만 전달 (권장):**

```json
{
  "academyKey": "오엠에A 실용음악학원",
  "lessonId": 42,
  "includeStt": true,
  "useTemplate": false,
  "targetKeyword": "삼송 보컬학원"
}
```

**방법 B — recordings JSON 직접 전달:**
{
  "academyKey": "오엠에A 실용음악학원",
  "lessonTitle": "호흡 교정",
  "keyCoachingPoints": "복식호흡, 자세 교정",
  "teacherName": "전창영",
  "includeStt": true,
  "maxSttClips": 12,
  "recordings": [
    {
      "recordingId": 101,
      "title": "고음 구간",
      "audioUrl": "https://your-coda-storage/lesson-101.webm",
      "processingStatus": "ready"
    }
  ],
  "sttSnippets": [],
  "tags": [
    { "timestampMs": 12000, "type": "breathing", "note": "호흡 짧음" }
  ],
  "useTemplate": false,
  "targetKeyword": "삼송 보컬학원"
}
```

**응답:** `markdown`, `naver`, `jsonLd`, `sourceText`, `sttSnippets`, `draftId`

**헬스:** `GET /api/v1/health` — `codaDb`: `ok` | `not_configured`

---

## 3) CODA 쪽 연결 예시 (TypeScript)

`.env` (CODA):

```
AEO_API_BASE_URL=http://127.0.0.1:8787
AEO_API_KEY=your-shared-secret
```

```typescript
async function generateAeoFromLessonId(lessonId: number) {
  const res = await fetch(`${process.env.AEO_API_BASE_URL}/api/v1/drafts/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.AEO_API_KEY}`,
    },
    body: JSON.stringify({
      academyKey: teacher.academyName,
      lessonId,
      includeStt: true,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

레슨 ID 없이 recordings를 직접 보내는 방식:

```typescript
async function generateAeoFromLesson(lesson: Lesson, recordings: LessonRecording[]) {
  const res = await fetch(`${process.env.AEO_API_BASE_URL}/api/v1/drafts/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.AEO_API_KEY}`,
    },
    body: JSON.stringify({
      academyKey: teacher.academyName,
      lessonTitle: lesson.title,
      keyCoachingPoints: lesson.keyCoachingPoints,
      teacherName: teacher.fullName,
      includeStt: true,
      recordings: recordings.map((r) => ({
        recordingId: r.id,
        title: r.title,
        audioUrl: r.audioUrl,
        processingStatus: r.processingStatus,
        createdAt: r.createdAt,
      })),
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

기존 `server/aeo/generateAeoDraft.ts` 로컬 생성 대신 위 API를 호출하면 됩니다.

---

## 4) `.env` (AEO 앱)

```bash
AEO_API_KEY=change-me-in-production
CODA_ALLOWED_ORIGINS=http://localhost:5000,http://127.0.0.1:5000
CODA_DATABASE_URL=postgresql://...   # CODA Supabase (선택 — UI/API 자동 불러오기)
CODA_TEACHER_NAME=전창영
```

`AEO_API_KEY`가 비어 있으면 API는 로컬 개발용으로 키 검증을 건너뜁니다.

---

## 5) Python 모듈

| AEO | CODA 원본 |
|-----|-----------|
| `core/coda_import.py` | `buildLessonSource.ts` + `pickRecordingsForStt` |
| `core/stt.py` `transcribe_audio_url` | `stt.ts` |
| `db/coda_connection.py` | CODA Postgres 연결 |
| `db/coda_repo.py` | 레슨·녹음·태그 읽기 |
| `services/coda_service.py` | `generate_from_coda_lesson_id` |
| `web/api_v1.py` | HTTP API |

---

## 6) CODA 후속 작업

1. 레sson AEO 버튼 → `POST /api/v1/drafts/generate` 호출
2. `server/aeo/*` 로컬 OpenAI 호출 제거 (또는 feature flag)
3. CORS origin을 CODA 배포 URL로 추가
