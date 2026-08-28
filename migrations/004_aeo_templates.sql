-- 상위 노출 포스팅 구조 템플릿 캐시 (AEO Template Scraper)
CREATE TABLE IF NOT EXISTS aeo_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_keyword TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('naver', 'google')),
  source_urls TEXT[] NOT NULL DEFAULT '{}',
  template_json JSONB NOT NULL,
  raw_extractions JSONB NOT NULL DEFAULT '[]',
  fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (target_keyword, channel)
);

CREATE INDEX IF NOT EXISTS aeo_templates_keyword_idx
  ON aeo_templates (target_keyword, channel, fetched_at DESC);
