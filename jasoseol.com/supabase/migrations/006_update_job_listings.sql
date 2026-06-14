-- duty_group_ids 컬럼 추가 (자소설닷컴 대분류 직무 ID 배열)
ALTER TABLE job_listings ADD COLUMN IF NOT EXISTS duty_group_ids integer[] DEFAULT '{}';

-- d_day는 스크랩 시점 기준 문자열로 부정확 → 제거 (end_date로 실시간 계산)
ALTER TABLE job_listings DROP COLUMN IF EXISTS d_day;

-- 직무 필터 성능을 위한 GIN 인덱스
CREATE INDEX IF NOT EXISTS idx_job_listings_duty_group_ids ON job_listings USING GIN (duty_group_ids);
