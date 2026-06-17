# LinkedIn Job Scraper

This directory contains a requests-based job search scraper for [LinkedIn](https://www.linkedin.com/) using public guest endpoints.

Because this scraper does not use Selenium, it is extremely fast and lightweight. It runs on simple HTTP GET requests, which makes it highly reliable for scheduled automation.

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

## Running the Scraper

### Examples

1. **Dry run (No database insert, print results to console):**
   Searches for "software engineer" in Singapore, fetches up to 25 jobs (1 page offset), and prints the output:
   ```bash
   python scraper.py --keyword "software engineer" --location "Singapore" --max-pages 1 --no-supabase
   ```

2. **Normal run (Save results to Supabase):**
   Performs a search and saves all extracted jobs to the `unified_job_listings` table:
   ```bash
   python scraper.py --keyword "data analyst" --location "Singapore" --max-pages 2
   ```

### Command Line Arguments

- `-q`, `--keyword`: Search keyword (default: `None`, queries all job listings)
- `-l`, `--location`: Search location (default: `"Singapore"`)
- `-p`, `--max-pages`: Maximum pages to scrape (each page contains 25 listings) (default: `2`)
- `--no-supabase`: Run in dry-run mode, printing results to stdout and skipping database insertion.
- `--delay`: Delay in seconds between requests to prevent rate-limiting (default: `3.0`)
