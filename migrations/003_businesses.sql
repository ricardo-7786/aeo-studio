-- 범용 AEO 앱: 업체(워크스페이스) 테이블
CREATE TABLE IF NOT EXISTS businesses (
  id SERIAL PRIMARY KEY,
  business_key TEXT NOT NULL UNIQUE,
  industry TEXT NOT NULL DEFAULT 'general',
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
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS businesses_industry_idx ON businesses (industry);

-- academy_aeo_profiles → businesses (레거시 마이그레이션)
INSERT INTO businesses (
  business_key, industry, name, location, address, phone, url, services, evidence,
  geo_lat, geo_lng, price_range, opening_hours
)
SELECT
  academy_key,
  'education',
  name,
  location,
  address,
  phone,
  url,
  services,
  evidence,
  geo_lat,
  geo_lng,
  price_range,
  opening_hours
FROM academy_aeo_profiles
WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'academy_aeo_profiles')
ON CONFLICT (business_key) DO NOTHING;

-- 기본 시드 (없을 때만)
INSERT INTO businesses (
  business_key, industry, name, location, address, phone, url, services, evidence,
  geo_lat, geo_lng, price_range, opening_hours
) VALUES (
  '오엠에이 실용음악학원',
  'education',
  '오엠에이 실용음악학원',
  '경기도 고양시 화정역 2번 출구',
  '경기도 고양시 덕양구 화중로 60 화정빌딩 507-B호',
  '031-973-5001',
  'https://oma-nd39.vercel.app',
  '보컬, 미디작곡, 기타, 피아노, 베이스, 드럼',
  '20년 경력 실용음악 교수 직강 및 CODA 레슨 피드백 시스템 운용',
  '37.6334',
  '126.8327',
  '$$',
  'Mo-Fr 14:00-22:00, Sa 13:00-19:00'
)
ON CONFLICT (business_key) DO NOTHING;
