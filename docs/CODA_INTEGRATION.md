# CODA ↔ 학원홍보 AEO 연동

## 역할 분담

| | CODA (Vocal-Coach) | 학원홍보 AEO |
|---|---|---|
| 레슨 녹음 | ✅ (학생·강사용) | ❌ (별도 홍보용 녹음 UI) |
| STT | (선택) API 위임 | ✅ |
| AEO/SEO 초안 | API 호출만 | ✅ (메인) |
| 발행·순위 추적 | ❌ | ✅ (예정) |

## CODA에서 넘기는 데이터 (API 계약 예시)

```http
POST /api/v1/drafts/generate
Authorization: Bearer <academy-api-key>
Content-Type: application/json

{
  "academyKey": "오엠에이 실용음악학원",
  "lessonTitle": "그겨울 발음 수정",
  "keyCoachingPoints": "...",
  "sttSnippets": [
    { "title": "포인트 1", "text": "웃음도 기대도..." },
    { "title": "포인트 2", "text": "..." }
  ]
}
```

응답: `tistory.markdown`, `naver.title/body/keywords`, `jsonLd`, `sourceText`

## TypeScript 참조 (`packages/aeo-core-ts/`)

CODA `server/aeo/*` 와 동기화된 TypeScript 원본입니다.

- CODA가 당분간 로컬 생성을 유지할 때 diff 기준
- 향후 `@academy-aeo/core` npm 패키지 또는 HTTP API로 통합

## Python 코어 (`core/`)

| 모듈 | CODA 원본 |
|------|-----------|
| `prompts.py` | `optimize.ts` 프롬프트 |
| `naver_utils.py` | `buildNaverLocalKeywords`, `stripNaverMarkdown` |
| `build_source.py` | `buildLessonSource.ts` |
| `stt.py` | `stt.ts` |
| `dual_channel.py` | `optimizeLessonToDualChannels` |
| `draft_generator.py` | `generateAeoDraft.ts` |

## CODA 쪽 후속 작업

1. `server/aeo/*` → AEO API 클라이언트로 교체 (또는 `packages/aeo-core-ts` 공유)
2. 레슨 화면 버튼은 유지, 생성은 AEO 서비스 호출
3. `lessons.aeo_draft_*` 컬럼은 `draft_id` 참조 또는 제거
