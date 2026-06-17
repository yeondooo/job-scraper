# written in python 3.9+
# -*- coding: utf-8 -*-
# linkedin.com - LinkedIn Jobs Scraper using Public Guest API
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

from typing import Optional

load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("💡 Supabase client initialized successfully.")
    except Exception as e:
        print(f"⚠️ Failed to initialize Supabase: {e}")

BASE_URL = "https://www.linkedin.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}


def fetch_page(url: str, params: dict = None, delay: float = 3.0) -> Optional[str]:
    """Fetch HTML from a URL using requests."""
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                time.sleep(delay)
                return resp.text
            print(f"  HTTP {resp.status_code} — Retry {attempt + 1}/3")
            if resp.status_code in (429, 502, 503):
                time.sleep(10 * (attempt + 1))
                continue
        except Exception as e:
            print(f"  Request error — Retry {attempt + 1}/3: {e}")
            time.sleep(3 * (attempt + 1))
    return None


def parse_list_page(html: str) -> list[dict]:
    """Parse job list HTML and extract listings."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li")
    jobs = []
    
    for card in cards:
        try:
            # Job Title Link
            link_el = card.select_one("a.base-card__full-link")
            if not link_el:
                continue
            title = link_el.get_text(strip=True)
            href = link_el.get("href", "")
            
            # Extract job_id from URL
            # e.g., https://sg.linkedin.com/jobs/view/software-engineer-1234567890
            job_id = None
            entity_urn = card.get("data-entity-urn", "")
            if "jobPosting:" in entity_urn:
                job_id = entity_urn.split("jobPosting:")[-1]
            else:
                job_id_match = re.search(r"/view/.*?-(\d+)\??", href)
                if not job_id_match:
                    job_id_match = re.search(r"/view/(\d+)", href) or re.search(r"(\d+)\?", href)
                job_id = job_id_match.group(1) if job_id_match else None
                
            if not job_id:
                continue
                
            job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
            
            # Company Name
            company_el = card.select_one(".base-search-card__subtitle")
            company_name = company_el.get_text(strip=True) if company_el else None
            
            # Location
            location_el = card.select_one(".job-search-card__location")
            location = location_el.get_text(strip=True) if location_el else None
            
            # Date Range / Date Listed
            time_el = card.select_one("time")
            date_range = time_el.get_text(strip=True) if time_el else None
            
            jobs.append({
                "job_id": job_id,
                "url": job_url,
                "title": title,
                "company_name": company_name,
                "location": location,
                "date_range": date_range
            })
        except Exception as ex:
            print(f"  ⚠️ Error parsing card: {ex}")
            
    return jobs


def parse_detail_page(html: str) -> dict:
    """Parse individual job details HTML."""
    soup = BeautifulSoup(html, "html.parser")
    detail = {}
    
    # Extract Description
    desc_el = soup.select_one(".description__text") or soup.select_one(".show-more-less-html__markup")
    if desc_el:
        detail["tasks"] = desc_el.get_text(separator="\n", strip=True)
        
    # Extract Employment Type and Industry from criteria items
    criteria_items = soup.select(".description__job-criteria-item")
    for item in criteria_items:
        header_el = item.select_one(".description__job-criteria-subheader")
        val_el = item.select_one(".description__job-criteria-text")
        if header_el and val_el:
            header_text = header_el.get_text(strip=True).lower()
            val_text = val_el.get_text(strip=True)
            if "employment type" in header_text:
                detail["employment_type"] = val_text
            elif "industries" in header_text:
                detail["industry"] = val_text
                
    return detail


def save_to_supabase(rows: list[dict]):
    """Upsert data to Supabase."""
    if not supabase:
        print("⚠️ Supabase client not initialized. Skipping database save.")
        return
        
    for attempt in range(3):
        try:
            supabase.table("unified_job_listings").upsert(
                rows, on_conflict="source,source_job_id"
            ).execute()
            print(f"  💾 Supabase saved: {len(rows)} rows.")
            return
        except Exception as e:
            print(f"  Retry save {attempt + 1}/3: {e}")
            time.sleep(3)
    print("  ❌ Failed to save data to Supabase.")


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Jobs Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-q", "--keyword", type=str, default=None,
                        help="Search keyword (default: None, queries all jobs)")
    parser.add_argument("-l", "--location", type=str, default="Singapore",
                        help="Search location (default: 'Singapore')")
    parser.add_argument("-p", "--max-pages", type=int, default=2,
                        help="Maximum pages to scrape (default: 2, 25 jobs per page)")
    parser.add_argument("--no-supabase", action="store_true", default=False,
                        help="Skip saving to Supabase (Dry run)")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Delay in seconds between requests (default: 3.0)")

    args = parser.parse_args()
    
    print("🚀 Starting LinkedIn Jobs Scraper")
    print(f"   Keyword: {args.keyword if args.keyword else 'All (No Filter)'}")
    print(f"   Location: {args.location}")
    print(f"   Max Pages: {args.max_pages} ({args.max_pages * 25} jobs)")
    print(f"   No Supabase: {args.no_supabase}")
    print(f"   Delay: {args.delay}s")
    print()
    
    all_jobs = []
    scraped_at = datetime.utcnow().isoformat() + "Z"
    
    # Phase 1: Fetch Job List
    list_url = f"{BASE_URL}/jobs-guest/jobs/api/seeMoreJobPostings/search"
    for page in range(1, args.max_pages + 1):
        start = (page - 1) * 25
        params = {
            "location": args.location,
            "start": start
        }
        if args.keyword:
            params["keywords"] = args.keyword
            
        print(f"[Page {page}/{args.max_pages}] Fetching job list...")
        html = fetch_page(list_url, params=params, delay=args.delay)
        if not html:
            print("   Failed to fetch page. Stopping search.")
            break
            
        jobs = parse_list_page(html)
        if not jobs:
            print("   No more jobs found. Stopping search.")
            break
            
        all_jobs.extend(jobs)
        
    print(f"\n📋 Found {len(all_jobs)} jobs. Scraping detail pages...")
    
    # Phase 2: Fetch Details
    final_rows = []
    for i, job in enumerate(all_jobs, 1):
        print(f"[{i}/{len(all_jobs)}] Job: {job['title']} @ {job['company_name']}")
        
        detail_url = f"{BASE_URL}/jobs-guest/jobs/api/jobPosting/{job['job_id']}"
        detail_html = fetch_page(detail_url, delay=args.delay)
        
        if detail_html:
            detail = parse_detail_page(detail_html)
            job.update(detail)
            
        row = {
            "source": "linkedin",
            "source_job_id": job["job_id"],
            "url": job["url"],
            "title": job["title"],
            "company_name": job.get("company_name"),
            "location": job.get("location"),
            "date_range": job.get("date_range"),
            "tasks": job.get("tasks"),
            "employment_type": job.get("employment_type"),
            "industry": job.get("industry"),
            "scraped_at": scraped_at
        }
        final_rows.append(row)
        
        if args.no_supabase:
            print(f"   Details parsed:")
            print(f"     Employment: {row['employment_type']}")
            print(f"     Industry: {row['industry']}")
            print(f"     Description (first 100 chars): {row.get('tasks', '')[:100].replace(chr(10), ' ')}...")
            
    # Phase 3: Save to Supabase
    if not args.no_supabase and final_rows:
        print(f"\n💾 Upserting {len(final_rows)} records to Supabase...")
        batch_size = 50
        for i in range(0, len(final_rows), batch_size):
            batch = final_rows[i:i + batch_size]
            save_to_supabase(batch)
    else:
        print("\nℹ️ Dry run completed. Supabase save skipped.")
        
    print("🏁 Scraper finished.")


if __name__ == "__main__":
    main()
