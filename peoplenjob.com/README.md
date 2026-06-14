# peoplenjob.com 스크래퍼

외국기업 취업전문 사이트 [피플앤잡](https://www.peoplenjob.com)의 채용 공고를 스크래핑하여 Supabase에 저장합니다.

## 설치

```bash
pip install -r requirements.txt
```

## 환경 설정

`.env.example`을 `.env`로 복사한 후 Supabase 인증 정보를 입력합니다:

```bash
cp .env.example .env
```

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
```

## 데이터베이스 설정

Supabase SQL Editor에서 `supabase/migrations/001_create_peoplenjob_listings.sql`을 실행하여 테이블을 생성합니다.

## 사용법

```bash
# 기본 사용 (5페이지 수집, 상세 포함)
python scraper.py

# 키워드 검색
python scraper.py -q "마케팅"

# 최근 7일, 신입 채용만
python scraper.py -p 7 -c 1

# 목록만 빠르게 수집 (상세 스킵, 20페이지)
python scraper.py --no-detail --max-pages 20

# 요청 간격 조절 (2초)
python scraper.py --delay 2.0
```

## CLI 옵션

| 옵션 | 단축 | 설명 | 기본값 |
|------|------|------|--------|
| `--keyword` | `-q` | 검색 키워드 | 없음 |
| `--period` | `-p` | 기간 필터 (1/3/7/14/30일) | `all` |
| `--career-level` | `-c` | 경력 수준 (1=신입, 2=사원, 3=과장, 4=부장) | 없음 |
| `--location` | `-l` | 근무지 필터 | 없음 |
| `--max-pages` | | 최대 수집 페이지 수 | `5` |
| `--no-detail` | | 상세 페이지 크롤링 스킵 | `False` |
| `--delay` | | 요청 간 딜레이(초) | `1.0` |

## 수집 데이터

| 필드 | 소스 | 설명 |
|------|------|------|
| `job_id` | 목록 | 채용 공고 고유 ID |
| `url` | 목록 | 상세 페이지 URL |
| `title` | 목록 | 채용 제목 |
| `company_name` | 목록/상세 | 회사명 |
| `location` | 목록 | 근무지 |
| `career_level` | 목록 | 경력 수준 |
| `date_range` | 목록 | 채용 기간 |
| `tasks` | 상세 | 업무내용 |
| `requirements` | 상세 | 자격요건 |
| `employment_type` | 상세 | 고용형태 |
| `salary` | 상세 | 급여사항 |
| `company_address` | 상세 | 회사 주소 |
| `company_website` | 상세 | 회사 웹사이트 |
| `company_intro` | 상세 | 회사 소개 |

## 의존성

- `requests` — HTTP 요청
- `beautifulsoup4` + `lxml` — HTML 파싱
- `python-dotenv` — 환경변수 관리
- `supabase` — 데이터베이스 클라이언트
