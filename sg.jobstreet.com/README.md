# JobStreet SG Scraper

This directory contains a Selenium-based job search scraper for [JobStreet Singapore](https://sg.jobstreet.com/).

Because JobStreet Singapore is protected by Cloudflare anti-bot security, standard HTTP requests (`requests`) return `403 Forbidden`. This scraper launches a Selenium webdriver (Chrome) to load the pages and extract listings, bypassing basic bot challenges.

## Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   Copy `.env.example` to `.env` and fill in your Supabase connection parameters:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and configure:
   ```env
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   ```

3. **Make sure Google Chrome is installed:**
   The scraper uses Selenium Chrome webdriver. `webdriver-manager` will automatically fetch and manage the matching ChromeDriver version for your installed Google Chrome browser.

## Running the Scraper

### Examples

1. **Dry run (Headless mode, no database insert):**
   This launches Chrome in the background, searches for "software engineer", parses the first page, and prints the extracted jobs to console without connecting to Supabase:
   ```bash
   python scraper.py --keyword "software engineer" --max-pages 1 --headless --no-supabase
   ```

2. **Normal run (Visible browser, save to Supabase):**
   Runs a search, displays the browser, and saves all extracted jobs to the `unified_job_listings` table:
   ```bash
   python scraper.py --keyword "data analyst" --max-pages 3
   ```

### Command Line Arguments

- `-q`, `--keyword`: Search keyword (default: `"software engineer"`)
- `-p`, `--max-pages`: Maximum pages to scrape (default: `5`)
- `--headless`: Run Chrome in headless mode (no UI displayed)
- `--no-supabase`: Run in dry-run mode, printing results to stdout and skipping database insertion.
- `--delay`: Delay in seconds between page requests to mimic human behavior (default: `3.0`)
