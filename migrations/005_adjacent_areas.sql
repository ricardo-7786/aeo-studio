-- 인접 상권 키워드 (쉼표 구분: 화정,행신,원당,삼송)
ALTER TABLE businesses
  ADD COLUMN IF NOT EXISTS adjacent_areas TEXT NOT NULL DEFAULT '';
