# written in python 3.10
# -*- coding: utf-8 -*-
# kowork.kr - No.1 외국인 채용 플랫폼 채용 공고 스크래퍼
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

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# local testing backup using Jobs client keys if environment is not set
if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ Environment variables SUPABASE_URL/SUPABASE_KEY not set. Checking fallback...")
    # try to load from POW_web/.env if possible (for local execution convenience)
    try:
        pow_env_path = os.path.join(os.path.dirname(__file__), "../../pow/POW_web/.env")
        if os.path.exists(pow_env_path):
            with open(pow_env_path) as f:
                for line in f:
                    if line.startswith("VITE_JOBS_SUPABASE_URL="):
                        SUPABASE_URL = line.split("=")[1].strip()
                    elif line.startswith("VITE_JOBS_SUPABASE_ANON_KEY="):
                        SUPABASE_KEY = line.split("=")[1].strip()
            print("💡 Loaded fallback keys from POW_web/.env")
    except Exception as e:
         pass

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables or env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_URL = "https://kowork.kr"
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
    """메인 페이지에서 채용 공고 카드를 파싱합니다."""
    soup = BeautifulSoup(html, "html.parser")
    # id가 post-list-post-card-<id> 형식인 a 태그들을 찾습니다.
    cards = soup.find_all("a", id=re.compile(r"^post-list-post-card-\d+"))
    jobs = []

    print(f"  🔍 목록 페이지에서 채용공고 카드 {len(cards)}개 발견")

    for card in cards:
        href = card.get("href", "")
        job_id_match = re.search(r"/post/(\d+)", href)
        if not job_id_match:
            continue
        job_id = job_id_match.group(1)
        url = f"{BASE_URL}/post/{job_id}"

        # 제목
        title_p = card.find("p", class_=re.compile(r"web-h-sbd-w-16|web-h-bd-w-18"))
        title = title_p.get_text(strip=True) if title_p else "N/A"

        # 회사명 및 직종(산업군)
        company_name = None
        industry = None
        spans = card.select("div.flex.gap-1 > span")
        if len(spans) > 0:
            company_name = spans[0].get_text(strip=True)
        if len(spans) > 1:
            industry = spans[1].get_text(strip=True)

        # 마감일 (D-Day)
        deadline_p = card.find("p", class_=re.compile(r"text-gray-05"))
        deadline = deadline_p.get_text(strip=True) if deadline_p else "N/A"

        # 데스크톱용 필터 알약들 (위치, 근무 형태 등)
        desktop_div = card.find("div", class_=lambda c: c and "hidden" in c and "md:flex" in c)
        location = None
        employment_type = None
        if desktop_div:
            pills = [p.get_text(strip=True) for p in desktop_div.find_all("p", class_="bg-gray-01")]
            if len(pills) > 0:
                location = pills[0]
            if len(pills) > 1:
                employment_type = pills[1]

        # 비자 지원 태그 (예: E-7 비자지원)
        visa_pill = card.find("p", class_=lambda c: c and "bg-[#FFF1F0]" in c)
        visa_type = visa_pill.get_text(strip=True) if visa_pill else None

        # 로고 이미지
        logo_el = card.select_one("img")
        logo_url = logo_el.get("src") if logo_el else None

        jobs.append({
            "job_id": job_id,
            "url": url,
            "title": title,
            "company_name": company_name,
            "location": location,
            "employment_type": employment_type,
            "visa_type": visa_type,
            "deadline": deadline,
            "industry": industry,
            "logo_url": logo_url,
        })

    return jobs


def parse_detail_page(html: str) -> dict:
    """채용 상세 페이지에서 주요 업무, 자격 요건, 우대 사항, 선호 비자, 복리 후생 등을 파싱합니다."""
    soup = BeautifulSoup(html, "html.parser")
    detail = {}

    # 1. 주요 텍스트 섹션들 (flex flex-col gap-4) 파싱
    sections = soup.find_all("div", class_="flex flex-col gap-4")
    for s in sections:
        header = s.find(["h1", "h2", "h3", "h4", "h5", "p", "span"])
        if not header:
            continue
        header_title = header.get_text(strip=True)
        content = s.get_text(separator="\n", strip=True)
        
        # 헤더 타이틀 텍스트 제거
        lines = content.split("\n")
        if len(lines) > 1 and lines[0].strip() == header_title:
            section_text = "\n".join(lines[1:])
        else:
            section_text = content

        if header_title == "주요 업무":
            detail["tasks"] = section_text
        elif header_title == "자격 요건":
            detail["requirements"] = section_text
        elif header_title == "우대 사항":
            detail["preferred"] = section_text
        elif header_title == "선호 비자":
            detail["visas_preferred"] = section_text
        elif header_title == "복리 후생":
            detail["benefits"] = section_text

    # 2. 계약 형태, 직무, 급여, 상세 주소 정보 파싱 (bg-gray-00 div)
    info_div = soup.find("div", class_=lambda c: c and "rounded-xl" in c and "bg-gray-00" in c)
    if info_div:
        for child in info_div.find_all("div", recursive=False):
            p_tags = child.find_all("p")
            label = p_tags[0].get_text(strip=True) if len(p_tags) > 0 else None
            value = p_tags[1].get_text(strip=True) if len(p_tags) > 1 else None
            
            # 단일 자식이나 구조가 다를 때를 대비해 예외 처리
            if label and not value:
                value = child.get_text(strip=True).replace(label, "", 1).strip()
            
            if label == "계약형태":
                detail["employment_type"] = value
            elif label == "급여":
                detail["salary"] = value
            elif label == "근무지":
                # 주소 복사 버튼 텍스트 제거
                if value and "주소 복사" in value:
                    value = value.replace("주소 복사", "").strip()
                detail["location_detail"] = value

    return detail


def save_to_supabase(rows: list[dict]):
    """Supabase에 upsert로 저장합니다."""
    if not rows:
        return
    for attempt in range(3):
        try:
            supabase.table("kowork_listings").upsert(
                rows, on_conflict="job_id"
            ).execute()
            print(f"  💾 Supabase 저장 완료: {len(rows)}건")
            return
        except Exception as e:
            print(f"  저장 재시도 {attempt + 1}/3: {e}")
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Kowork job scraper")
    parser.add_argument("--limit", type=int, default=15, help="스크랩할 최대 공고 개수 (기본 15)")
    args = parser.parse_args()

    print(f"🚀 Kowork 스크래퍼 시작: {datetime.now().isoformat()}")
    
    # 메인 페이지 로드
    html = fetch_page(BASE_URL)
    if not html:
        print("❌ 메인 페이지 로드 실패")
        return

    # 공고 목록 파싱
    jobs = parse_list_page(html)
    if not jobs:
        print("❌ 파싱된 채용 공고가 없습니다.")
        return

    # 필요한 개수만큼 슬라이싱
    jobs = jobs[:args.limit]
    final_jobs = []

    for idx, job in enumerate(jobs):
        print(f"  👉 [{idx+1}/{len(jobs)}] 상세 정보 수집 중: {job['title']} ({job['company_name']})")
        detail_html = fetch_page(job["url"], delay=1.5)
        if detail_html:
            detail_info = parse_detail_page(detail_html)
            # 수집된 정보 머지 (상세 페이지에서 계약형태나 근무지가 더 상세할 수 있으므로 덮어씀)
            job.update(detail_info)
        
        # DB 컬럼 규격에 맞춰 정리
        final_jobs.append({
            "job_id": job.get("job_id"),
            "url": job.get("url"),
            "title": job.get("title"),
            "company_name": job.get("company_name"),
            "location": job.get("location_detail") or job.get("location"),
            "employment_type": job.get("employment_type"),
            "visa_type": job.get("visa_type"),
            "deadline": job.get("deadline"),
            "industry": job.get("industry"),
            "logo_url": job.get("logo_url"),
            "tasks": job.get("tasks"),
            "requirements": job.get("requirements"),
            "preferred": job.get("preferred"),
            "visas_preferred": job.get("visas_preferred"),
            "benefits": job.get("benefits"),
        })

    # Supabase 저장
    save_to_supabase(final_jobs)
    print("🏁 스크랩 완료!")


if __name__ == "__main__":
    main()
