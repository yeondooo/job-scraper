# written in python 3.10
# -*- coding: utf-8 -*-
# peoplenjob.com - 외국기업 취업전문 사이트 채용 공고 스크래퍼
# Dependency: requests, beautifulsoup4, lxml, python-dotenv, supabase

import argparse
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_URL = "https://www.peoplenjob.com"
JOBS_URL = f"{BASE_URL}/jobs"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_page(url: str, delay: float = 1.0) -> str | None:
    """URL에서 HTML을 가져옵니다. 최대 3회 재시도합니다."""
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                time.sleep(delay)
                return resp.text
            print(f"  HTTP {resp.status_code} — 재시도 {attempt + 1}/3")
            if resp.status_code in (502, 503):
                time.sleep(10)
                continue
        except Exception as e:
            print(f"  요청 오류 — 재시도 {attempt + 1}/3: {e}")
            time.sleep(3 * (attempt + 1))
    return None


def parse_list_page(html: str) -> list[dict]:
    """채용 목록 페이지에서 jd-card 카드를 파싱합니다."""
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.jd-card")
    jobs = []

    for card in cards:
        # 제목 + URL
        title_el = card.select_one("h5.jd-card-title > a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # job_id 추출
        job_id_match = re.search(r"/jobs/(\d+)", href)
        job_id = job_id_match.group(1) if job_id_match else None
        if not job_id:
            continue

        # 회사명
        company_el = card.select_one("a.jd-card-company")
        company_name = company_el.get_text(strip=True) if company_el else None

        # 근무지
        location_el = card.select_one("span.jd-card-meta-location-text")
        location = location_el.get_text(strip=True) if location_el else None

        # 경력
        career_el = card.select_one("span.jd-card-meta-career-text")
        career_level = career_el.get_text(strip=True) if career_el else None

        # 기간
        date_el = card.select_one("span.jd-card-meta-static")
        date_range = None
        if date_el:
            date_text = date_el.get_text(strip=True)
            # 아이콘 텍스트 제거 후 날짜만 추출
            date_range = re.sub(r"^\s*", "", date_text).strip()

        jobs.append({
            "job_id": job_id,
            "url": url,
            "title": title,
            "company_name": company_name,
            "location": location,
            "career_level": career_level,
            "date_range": date_range,
        })

    return jobs


def parse_detail_page(html: str) -> dict:
    """채용 상세 페이지에서 세부 정보를 파싱합니다."""
    soup = BeautifulSoup(html, "lxml")
    detail = {}

    # jd-v2-section들에서 Tasks, Requirements 추출
    sections = soup.select("div.jd-v2-section")
    for section in sections:
        title_el = section.select_one("h4.jd-v2-section-title")
        if not title_el:
            continue
        section_title = title_el.get_text(strip=True)
        content_el = section.select_one("div.jd-v2-content div.view-editor")

        if section_title == "Tasks" and content_el:
            detail["tasks"] = content_el.get_text(separator="\n", strip=True)
        elif section_title == "Requirements" and content_el:
            detail["requirements"] = content_el.get_text(separator="\n", strip=True)

    # Information 테이블에서 고용형태, 급여 추출
    info_rows = soup.select("div.jd-v2-info-row")
    for row in info_rows:
        label_el = row.select_one("div.jd-v2-info-label")
        value_el = row.select_one("div.jd-v2-info-value")
        if not label_el or not value_el:
            continue

        label = label_el.get_text(strip=True)
        value = value_el.get_text(separator=" ", strip=True)

        if label == "고용형태":
            detail["employment_type"] = value
        elif label == "급여사항":
            detail["salary"] = value

    # 회사 정보
    company_link = soup.select_one("a.jd-v2-company-link")
    if company_link:
        detail["company_name_detail"] = company_link.get_text(strip=True)

    company_meta = soup.select_one("div.jd-company-card-meta")
    if company_meta:
        detail["company_address"] = company_meta.get_text(strip=True)

    company_links = soup.select_one("div.jd-company-card-links")
    if company_links:
        link_el = company_links.select_one("a")
        if link_el:
            detail["company_website"] = link_el.get_text(strip=True)

    company_intro = soup.select_one("div.jd-company-card-intro")
    if company_intro:
        detail["company_intro"] = company_intro.get_text(separator="\n", strip=True)

    return detail


def build_search_url(page: int = 1, keyword: str | None = None,
                     period: str | None = None,
                     career_level: int | None = None,
                     location: str | None = None,
                     field: str | None = None) -> str:
    """검색 조건에 따른 URL을 생성합니다."""
    params = []
    if keyword:
        params.append(f"q={requests.utils.quote(keyword)}")
    if field:
        params.append(f"field={field}")
    if period and period != "all":
        params.append(f"period={period}")
    if career_level:
        params.append(f"career_level={career_level}")
    if location:
        params.append(f"work_location_tag={requests.utils.quote(location)}")
    if page > 1:
        params.append(f"page={page}")

    query = "&".join(params)
    return f"{JOBS_URL}?{query}" if query else JOBS_URL


def save_to_supabase(rows: list[dict]):
    """Supabase에 upsert로 저장합니다."""
    if not rows:
        return
    for attempt in range(3):
        try:
            supabase.table("unified_job_listings").upsert(
                rows, on_conflict="source,source_job_id"
            ).execute()
            print(f"  💾 Supabase 저장 완료: {len(rows)}건")
            return
        except Exception as e:
            print(f"  저장 재시도 {attempt + 1}/3: {e}")
            time.sleep(3 * (attempt + 1))
    print("  ❌ 저장 실패 — 건너뜀")


def scrape_all(args):
    """전체 스크래핑을 실행합니다."""
    scraped_at = datetime.utcnow().isoformat() + "Z"
    total = 0
    all_jobs: list[dict] = []

    print(f"🔍 피플앤잡 스크래핑 시작")
    if args.keyword:
        print(f"   키워드: {args.keyword}")
    if args.period != "all":
        print(f"   기간: 최근 {args.period}일")
    if args.career_level:
        print(f"   경력: level {args.career_level}")
    print(f"   최대 페이지: {args.max_pages}")
    print(f"   상세 페이지: {'포함' if not args.no_detail else '스킵'}")
    print()

    # 1단계: 목록 페이지 수집
    for page in range(1, args.max_pages + 1):
        url = build_search_url(
            page=page,
            keyword=args.keyword,
            period=args.period,
            career_level=args.career_level,
            location=args.location,
        )
        print(f"📄 페이지 {page} 수집 중... ({url})")

        html = fetch_page(url, delay=args.delay)
        if not html:
            print("  요청 실패 — 종료")
            break

        jobs = parse_list_page(html)
        if not jobs:
            print("  채용 공고 없음 — 종료")
            break

        all_jobs.extend(jobs)
        total += len(jobs)
        print(f"  ✅ {len(jobs)}건 파싱 (누적 {total}건)")

    if not all_jobs:
        print("\n수집된 공고가 없습니다.")
        return

    # 2단계: 상세 페이지 수집 (옵션)
    if not args.no_detail:
        print(f"\n📋 상세 페이지 수집 중... (총 {len(all_jobs)}건)")
        for i, job in enumerate(all_jobs, 1):
            print(f"  [{i}/{len(all_jobs)}] {job['title'][:40]}...")
            detail_html = fetch_page(job["url"], delay=args.delay)
            if detail_html:
                detail = parse_detail_page(detail_html)
                job.update(detail)
                # 상세 페이지의 회사명이 더 정확할 수 있음
                if "company_name_detail" in job:
                    job["company_name"] = job.pop("company_name_detail")

    # 3단계: Supabase 저장
    print(f"\n💾 Supabase에 저장 중...")
    rows = []
    for job in all_jobs:
        row = {
            "source": "peoplenjob",
            "source_job_id": job["job_id"],
            "url": job["url"],
            "title": job["title"],
            "company_name": job.get("company_name"),
            "location": job.get("location"),
            "career_level": job.get("career_level"),
            "date_range": job.get("date_range"),
            "tasks": job.get("tasks"),
            "requirements": job.get("requirements"),
            "employment_type": job.get("employment_type"),
            "salary": job.get("salary"),
            "company_address": job.get("company_address"),
            "company_website": job.get("company_website"),
            "company_intro": job.get("company_intro"),
            "scraped_at": scraped_at,
        }
        rows.append(row)

    # 배치 단위로 저장 (50건씩)
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        save_to_supabase(batch)

    print(f"\n✅ 완료: 총 {total}건 수집 및 저장")


def main():
    parser = argparse.ArgumentParser(
        description="피플앤잡(peoplenjob.com) 채용 공고 스크래퍼",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python scraper.py                                  # 기본 5페이지 수집
  python scraper.py -q "마케팅" -p 7                  # 마케팅 키워드, 최근 7일
  python scraper.py -c 1 --max-pages 10              # 신입 채용, 10페이지
  python scraper.py --no-detail --max-pages 20       # 목록만 빠르게 수집
        """,
    )

    parser.add_argument("-q", "--keyword", type=str, default=None,
                        help="검색 키워드")
    parser.add_argument("-p", "--period", type=str, default="all",
                        choices=["all", "1", "3", "7", "14", "30"],
                        help="기간 필터 (일 수, 기본: all)")
    parser.add_argument("-c", "--career-level", type=int, default=None,
                        choices=[1, 2, 3, 4],
                        help="경력 수준 (1=신입, 2=사원, 3=대리/과장, 4=팀장/부장)")
    parser.add_argument("-l", "--location", type=str, default=None,
                        help="근무지 필터")
    parser.add_argument("--max-pages", type=int, default=5,
                        help="최대 수집 페이지 수 (기본: 5)")
    parser.add_argument("--no-detail", action="store_true",
                        help="상세 페이지 크롤링 스킵 (목록만 수집)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="요청 간 딜레이 초 (기본: 1.0)")

    args = parser.parse_args()
    scrape_all(args)


if __name__ == "__main__":
    main()
