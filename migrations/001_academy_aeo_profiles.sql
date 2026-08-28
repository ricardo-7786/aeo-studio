-- 학원별 AEO 홍보 프로필 (레거시 — 003_businesses.sql 로 대체 가능)
CREATE TABLE IF NOT EXISTS academy_aeo_profiles (
  id SERIAL PRIMARY KEY,
  academy_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  location TEXT NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  services TEXT NOT NULL DEFAULT '',
  evidence TEXT NOT NULL DEFAULT '',
  geo_lat TEXT,
  geo_lng TEXT,
  price_range TEXT NOT NULL DEFAULT '$$',
  opening_hours TEXT NOT NULL DEFAULT '',
  updated_by_user_id INTEGER,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
