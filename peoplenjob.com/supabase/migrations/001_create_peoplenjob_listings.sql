-- peoplenjob.com 채용 공고 테이블
CREATE TABLE IF NOT EXISTS peoplenjob_listings (
    job_id          text PRIMARY KEY,
    url             text,
    title           text,
    company_name    text,
    location        text,
    career_level    text,
    date_range      text,
    tasks           text,
    requirements    text,
    employment_type text,
    salary          text,
    company_address text,
    company_website text,
    company_intro   text,
    scraped_at      timestamptz DEFAULT now()
);

-- 회사명 검색을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_peoplenjob_company_name ON peoplenjob_listings (company_name);

-- 수집 시각 기준 정렬 인덱스
CREATE INDEX IF NOT EXISTS idx_peoplenjob_scraped_at ON peoplenjob_listings (scraped_at DESC);
