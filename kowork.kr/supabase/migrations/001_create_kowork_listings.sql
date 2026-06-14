-- kowork.kr 채용 공고 테이블
CREATE TABLE IF NOT EXISTS kowork_listings (
    job_id          text PRIMARY KEY,
    url             text,
    title           text,
    company_name    text,
    location        text,
    employment_type text,
    visa_type       text,
    deadline        text,
    industry        text,
    logo_url        text,
    tasks           text,
    requirements    text,
    preferred       text,
    visas_preferred text,
    benefits        text,
    scraped_at      timestamptz DEFAULT now()
);

-- 회사명 검색을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_kowork_company_name ON kowork_listings (company_name);

-- 수집 시각 기준 정렬 인덱스
CREATE INDEX IF NOT EXISTS idx_kowork_scraped_at ON kowork_listings (scraped_at DESC);
