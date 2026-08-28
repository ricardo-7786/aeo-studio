-- AEO 앱 전용: 생성 초안 저장 (CODA lessons.aeo_draft_* 대체)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS aeo_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  academy_key TEXT NOT NULL,
  lesson_title TEXT NOT NULL DEFAULT '',
  source_text TEXT NOT NULL,
  tistory_markdown TEXT,
  tistory_json_ld JSONB,
  naver_title TEXT,
  naver_body TEXT,
  naver_keywords TEXT[] DEFAULT '{}',
  stt_snippets JSONB DEFAULT '[]',
  generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS aeo_drafts_academy_key_idx ON aeo_drafts (academy_key, generated_at DESC);

-- (선택) 발행 URL·순위 추적용 — 추후 rank tracking MVP
CREATE TABLE IF NOT EXISTS published_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id UUID REFERENCES aeo_drafts(id) ON DELETE SET NULL,
  academy_key TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('naver', 'tistory', 'wordpress')),
  published_url TEXT NOT NULL,
  target_keyword TEXT,
  target_engine TEXT CHECK (target_engine IN ('naver', 'google')),
  current_rank INTEGER,
  previous_rank INTEGER,
  last_checked_at TIMESTAMP,
  is_monitored BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rank_tracking_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id UUID NOT NULL REFERENCES published_posts(id) ON DELETE CASCADE,
  rank INTEGER,
  checked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
