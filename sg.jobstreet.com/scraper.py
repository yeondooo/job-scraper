# written in python 3.9+
# -*- coding: utf-8 -*-
# sg.jobstreet.com - Singapore JobStreet Scraper using Selenium
# Dependency: selenium, beautifulsoup4, lxml, python-dotenv, supabase, webdriver-manager

import argparse
import os
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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

BASE_URL = "https://sg.jobstreet.com"


def init_driver(headless: bool = True) -> webdriver.Chrome:
    """Initialize Selenium Chrome WebDriver with evasion settings."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Evasion settings to bypass basic anti-bot systems
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Try using webdriver-manager to set up the driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Remove navigator.webdriver flag
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    
    return driver


def scrape_list_page(driver: webdriver.Chrome, url: str) -> list[dict]:
    """Parse search results page and extract list of job listings."""
    print(f"📄 Navigating to: {url}")
    driver.get(url)
    
    # Wait for job cards to load
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="job-card"], article[data-automation="normalJob"]'))
        )
    except Exception as e:
        print("⚠️ Timeout waiting for job cards or no results found.")
        print(f"   Current page title: '{driver.title}'")
        print(f"   Current URL: '{driver.current_url}'")
        # Let's check if Cloudflare challenge is shown
        if "Just a moment" in driver.title or "Cloudflare" in driver.page_source:
            print("❌ Blocked by Cloudflare Turnstile/Challenge. Manual intervention or Turnstile bypass required.")
        else:
            print(f"   Page snippet: {driver.page_source[:1000]}")
        return []

    # Get page source and parse with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, "lxml")
    cards = soup.select('article[data-testid="job-card"], article[data-automation="normalJob"], article[data-automation="premiumJob"]')
    print(f"   Found {len(cards)} job cards on this page.")
    
    jobs = []
    for card in cards:
        try:
            # Job Title Link
            title_el = card.select_one('[data-automation="jobTitle"]')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            
            # Extract job_id from URL (e.g. /job/74929312 or /en/job/74929312)
            job_id_match = re.search(r"/job/(\d+)", href)
            job_id = job_id_match.group(1) if job_id_match else None
            if not job_id:
                continue
            
            job_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            
            # Company Name
            company_el = card.select_one('[data-automation="jobCompany"]')
            company_name = company_el.get_text(strip=True) if company_el else None
            
            # Location
            location_el = card.select_one('[data-automation="jobLocation"]')
            location = location_el.get_text(strip=True) if location_el else None
            
            # Salary (optional)
            salary_el = card.select_one('[data-automation="jobSalary"]')
            salary = salary_el.get_text(strip=True) if salary_el else None
            
            # Date Range / Listing Date
            date_el = card.select_one('[data-automation="jobListingDate"]')
            date_range = date_el.get_text(strip=True) if date_el else None
            
            jobs.append({
                "job_id": job_id,
                "url": job_url,
                "title": title,
                "company_name": company_name,
                "location": location,
                "salary": salary,
                "date_range": date_range
            })
        except Exception as ex:
            print(f"   ⚠️ Error parsing card: {ex}")
            
    return jobs


def scrape_detail_page(driver: webdriver.Chrome, url: str) -> dict:
    """Parse individual job listing page to extract description and details."""
    print(f"🔗 Detail Page: {url}")
    driver.get(url)
    
    detail = {}
    try:
        # Wait for description or details element
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-automation="jobAdDetails"], [data-automation="jobDescription"]'))
        )
    except Exception as e:
        print(f"   ⚠️ Could not load job details page or element not found: {e}")
        return detail
    
    soup = BeautifulSoup(driver.page_source, "lxml")
    
    # Extract Description
    desc_el = soup.select_one('[data-automation="jobAdDetails"], [data-automation="jobDescription"]')
    if desc_el:
        detail["tasks"] = desc_el.get_text(separator="\n", strip=True)
        
    # Extract Employment Type (Work Type)
    work_type_el = soup.select_one('[data-automation="job-detail-work-type"]')
    if work_type_el:
        detail["employment_type"] = work_type_el.get_text(strip=True)
        
    # Extract Industry (Classification)
    class_el = soup.select_one('[data-automation="job-detail-classifications"]')
    if class_el:
        detail["industry"] = class_el.get_text(strip=True)
        
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
        description="JobStreet Singapore (sg.jobstreet.com) Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-q", "--keyword", type=str, default="software engineer",
                        help="Search keyword (default: 'software engineer')")
    parser.add_argument("-p", "--max-pages", type=int, default=5,
                        help="Maximum pages to scrape (default: 5)")
    parser.add_argument("--headless", action="store_true", default=False,
                        help="Run Chrome in headless mode")
    parser.add_argument("--no-supabase", action="store_true", default=False,
                        help="Skip saving to Supabase (Dry run)")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Delay in seconds between page requests (default: 3.0)")

    args = parser.parse_args()
    
    print("🚀 Starting JobStreet SG Scraper")
    print(f"   Keyword: {args.keyword}")
    print(f"   Max Pages: {args.max_pages}")
    print(f"   Headless: {args.headless}")
    print(f"   No Supabase: {args.no_supabase}")
    print(f"   Delay: {args.delay}s")
    print()
    
    driver = None
    try:
        driver = init_driver(headless=args.headless)
        
        all_jobs = []
        scraped_at = datetime.utcnow().isoformat() + "Z"
        
        # Phase 1: Scraping Search Results Pages
        for page in range(1, args.max_pages + 1):
            url = f"{BASE_URL}/jobs?keywords={args.keyword.replace(' ', '+')}&page={page}"
            print(f"\n[Page {page}/{args.max_pages}] Fetching job list...")
            
            jobs = scrape_list_page(driver, url)
            if not jobs:
                print("   No more job listings found or request blocked. Stopping search.")
                break
                
            all_jobs.extend(jobs)
            time.sleep(args.delay)
            
        print(f"\n📋 Found {len(all_jobs)} jobs. Scraping detail pages...")
        
        # Phase 2: Scraping Detail Pages
        final_rows = []
        for i, job in enumerate(all_jobs, 1):
            print(f"[{i}/{len(all_jobs)}] Job: {job['title']} @ {job['company_name']}")
            
            detail = scrape_detail_page(driver, job["url"])
            job.update(detail)
            
            row = {
                "source": "jobstreet_sg",
                "source_job_id": job["job_id"],
                "url": job["url"],
                "title": job["title"],
                "company_name": job.get("company_name"),
                "location": job.get("location"),
                "salary": job.get("salary"),
                "date_range": job.get("date_range"),
                "tasks": job.get("tasks"),
                "employment_type": job.get("employment_type"),
                "industry": job.get("industry"),
                "scraped_at": scraped_at
            }
            final_rows.append(row)
            
            if args.no_supabase:
                # Print parsed job details in dry run
                print(f"   Details parsed:")
                print(f"     Employment: {row['employment_type']}")
                print(f"     Industry: {row['industry']}")
                print(f"     Description (first 100 chars): {row.get('tasks', '')[:100].replace(chr(10), ' ')}...")
            
            time.sleep(args.delay)
            
        # Phase 3: Save to Supabase
        if not args.no_supabase and final_rows:
            print(f"\n💾 Upserting {len(final_rows)} records to Supabase...")
            # Batch upsert in chunks of 50
            batch_size = 50
            for i in range(0, len(final_rows), batch_size):
                batch = final_rows[i:i + batch_size]
                save_to_supabase(batch)
        else:
            print("\nℹ️ Dry run completed. Supabase save skipped.")
            
    except Exception as e:
        print(f"\n❌ An error occurred during scraping: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("\n🔌 Closing browser...")
            driver.quit()
        print("🏁 Scraper finished.")


if __name__ == "__main__":
    main()
