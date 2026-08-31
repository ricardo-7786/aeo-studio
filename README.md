# 학원홍보 AEO — Answer Engine Optimization 블로그 파이프라인

오프라인 실용음악학원의 레슨 기록·상담 메모·네이버 블로그 글을  
생성형 AI가 인용하기 쉬운 **AEO 최적화 포스트**로 변환한 뒤  
WordPress 또는 티스토리에 자동 발행하는 Python 파이프라인입니다.

## 프로젝트 구조

```
학원홍보 AEO/
├── main.py                 # 실행 진입점 (--dual: 티스토리+네이버 동시)
├── requirements.txt
├── env.example             # → .env 로 복사
├── packages/
│   └── aeo-core-ts/        # CODA server/aeo/* TypeScript 참조본
├── migrations/
│   ├── 001_academy_aeo_profiles.sql
│   └── 002_drafts_and_rank_tracking.sql
├── docs/
│   └── CODA_INTEGRATION.md # CODA 연동 가이드
├── samples/
│   └── lesson_note.txt
├── db/
│   ├── business_repo.py
│   ├── draft_repo.py
│   └── post_repo.py
├── services/
│   └── content_service.py
├── web/
│   ├── app.py              # FastAPI 웹 UI
│   ├── templates/
│   └── static/
├── scripts/
│   ├── db_migrate.py
│   ├── business_cli.py
│   └── register_post.py
├── config/
│   ├── settings.py
│   └── industry.py
├── core/
│   ├── prompts.py          # 업종별 AEO/네이버 프롬프트
│   ├── build_source.py     # STT 여러 개 → sourceText
│   ├── stt.py              # Whisper STT (+ URL)
│   ├── aeo_optimizer.py    # 티스토리 AEO
│   ├── naver_optimizer.py  # 네이버 SEO
│   ├── dual_channel.py     # 동시 생성
│   ├── draft_generator.py  # 녹음→STT→초안
│   └── schema_builder.py
└── publishers/
    ├── wordpress.py
    └── tistory.py
```

## 동작 흐름

1. **입력** — `--text` / `--file` / `--url` / `--audio`(여러 포인트 녹음)
2. **STT** — Whisper (포인트 녹음 여러 개 → 시간순 → 한 글)
3. **Dual 생성** — `--dual` 티스토리(AEO) + 네이버(SEO) 동시
4. **구조화 데이터** — Schema.org JSON-LD
5. **발행** — WordPress/티스토리 (네이버는 txt 복사)

## 설치

```bash
cd "학원홍보 AEO"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
# .env 에 OPENAI_API_KEY, 학원정보, WP/티스토리 자격증명 입력
```

## 실행

```bash
# 티스토리+네이버 동시 (--dual 권장)
python main.py --file ./samples/lesson_note.txt --dual --dry-run

# 포인트 녹음 여러 개 → STT → 한 블로그 글
python main.py --audio rec1.m4a --audio rec2.m4a --lesson-title "그겨울 발음" --dual --dry-run

# STT 스모크 테스트
python scripts/smoke_stt.py --file ./recordings/point1.m4a

# 직접 텍스트
python main.py --text "오늘 기타 레슨: 펜타토닉 포지션 이동 연습 20분..."

# 네이버 블로그 URL
python main.py --url "https://blog.naver.com/yourid/123456789"

# WordPress 발행
python main.py --file ./samples/lesson_note.txt --platform wordpress

# 티스토리 발행 + gpt-4o
python main.py --file ./samples/lesson_note.txt --platform tistory --model gpt-4o
```

성공 시 콘솔에 `SUCCESS`와 포스팅 URL이 출력됩니다.  
산출물(`output/`)에는 `.md`, `.html`, `.jsonld.json`, `.meta.json`이 저장됩니다.

## 멀티 업체 DB (범용 앱 1단계)

PostgreSQL 연결 후:

```bash
# .env 에 DATABASE_URL=postgresql://...
pip install -r requirements.txt
python scripts/db_migrate.py

# .env 업체 정보 → DB 시드
python scripts/business_cli.py seed-from-env

# 업체 추가 (다른 업종 예: 카페)
python scripts/business_cli.py add \
  --key "홍대-카페OO" \
  --name "OO카페" \
  --industry restaurant \
  --location "홍대입구역 3번 출구" \
  --services "브런치, 디저트, 원두"

python scripts/business_cli.py list
```

글 생성 시 업체 선택:

```bash
python main.py --file ./samples/lesson_note.txt --dual --dry-run \
  --business-key "오엠에이 실용음악학원"

# DB + 초안 저장
python main.py --file ./samples/lesson_note.txt --dual --dry-run \
  --business-key "오엠에이 실용음악학원" --save-draft
```

업종: `education` | `restaurant` | `clinic` | `fitness` | `beauty` | `general`

## 웹 UI + 발행 URL 등록 (범용 앱 2단계)

업종별 프롬프트 분기 + 브라우저에서 글 생성·초안·발행 URL 관리:

```bash
pip install -r requirements.txt
python scripts/db_migrate.py
python scripts/business_cli.py seed-from-env

# 웹 서버 (기본 http://127.0.0.1:8787)
python -m web.app
# 또는
uvicorn web.app:app --reload --port 8787
```

웹 화면:

| 메뉴 | 기능 |
|------|------|
| 글 생성 | 텍스트 / 음성 업로드 / 앱 내 녹음 → 티스토리(AEO) + 네이버(SEO) |
| 업체 관리 | 업종·위치·서비스 등록/수정 (업종별 프롬프트 자동 적용) |
| 초안 목록 | DB 저장된 초안 조회 |
| 발행 URL | 블로그에 붙여넣은 뒤 URL·키워드 등록 (순위 추적 3단계 준비) |

CLI로 발행 URL 등록:

```bash
python scripts/register_post.py \
  --business-key "오엠에A 실용음악학원" \
  --channel naver \
  --url "https://blog.naver.com/yourid/123456789" \
  --keyword "화정역 보컬학원"
```

`.env` 옵션: `WEB_HOST=127.0.0.1`, `WEB_PORT=8787`

## AEO Template Scraper (2→1→3)

| 단계 | 내용 | 상태 |
|------|------|------|
| 2 | DB `aeo_templates` + 파일 `.cache/` 캐시 | ✅ |
| 1 | SerpAPI/수동 URL → 구조 추출 → `/generate` 프롬프트 주입 | ✅ |
| 3 | 네이버 VIEW Playwright | ⏸ mobile URL + Jina 폴백 후에도 실패할 때만 |

```bash
# DB 마이그레이션 (DATABASE_URL 필요)
python scripts/db_migrate.py

# 템플릿만 추출 (CLI)
python scripts/fetch_template.py --keyword "화정역 보컬학원" --channel naver
python scripts/fetch_template.py --keyword "화정역 보컬" --url "https://blog.naver.com/..."

# .env
SERPAPI_KEY=your-serpapi-key
TEMPLATE_CACHE_HOURS=72
```

웹 `/generate` → **상위 노출 템플릿 적용** 체크 + 키워드 (+ 선택: 참고 URL)

## 키워드 로테이션

본점 지역(예: 화정)은 본문에 사실대로 두고, **제목·리드 지역**은 인접 상권을 날짜 + 발행 회차로 순환합니다. STT에서 고음 씹힘·호흡 부족 등이 보이면 제목 골격에 붙입니다.

```bash
# .env
BUSINESS_ADJACENT_AREAS=행신, 원당, 삼송

python scripts/db_migrate.py   # adjacent_areas 컬럼

python main.py --file ./samples/lesson_note.txt --dual --dry-run --focus-area 행신
```

웹 `/generate` → **키워드 로테이션**에서 지역을 고르거나 비워 두면 자동 순환.

## AEO 변환 규칙 (프롬프트에 고정)

- 모호한 형용사(“잘 가르치는”, “친절한”) 최소화
- 학원 고유명사·위치(지하철역)·수치/근거를 본문에 자연스럽게 포함
- 학원명·서비스명 표기 일관성 유지
- 제목·첫 단락 = “핵심 주제가 무엇인가?”에 1문장으로 답 가능한 결론형

## API 준비

### WordPress

1. 사용자 → 프로필 → **애플리케이션 비밀번호** 발급  
2. `.env`에 `WP_SITE_URL`, `WP_USERNAME`, `WP_APP_PASSWORD` 설정  
3. `PUBLISH_PLATFORM=wordpress`

### 티스토리

1. [티스토리 API 관리](https://www.tistory.com/guide/api/manage/register)에서 앱·토큰 발급  
2. `.env`에 `TISTORY_ACCESS_TOKEN`, `TISTORY_BLOG_NAME` 설정  
3. `PUBLISH_PLATFORM=tistory`  
4. `TISTORY_VISIBILITY`: `0` 비공개 / `3` 발행

## 라이선스·주의

- 네이버 블로그 수집은 **본인 소유·공개 글** 용도로만 사용하세요.  
- 원문에 없는 수치·성과를 AI가 날조하지 않도록 학원 `ACADEMY_EVIDENCE`만 주입합니다.
