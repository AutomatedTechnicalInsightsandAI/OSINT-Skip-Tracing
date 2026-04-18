# OSINT Skip-Tracing

Local Streamlit app for generating Florida real-estate leads from public records, then optionally enriching those leads with open-source contact research.

The project is currently tuned for Prime Coastal Funding workflows, with the strongest live path focused on Sarasota recent-purchase cash-out refinance prospects.

## What It Does

- Scrapes public county records with Playwright and BeautifulSoup
- Normalizes results into a CSV-friendly lead table
- Supports multiple lead strategies across Sarasota, Miami-Dade, and Broward
- Optionally performs skip tracing with Google dorking
- Saves each successful run to `exports/`
- Caches expensive lookups in `.cache/` so reruns are much faster

## Current Lead Types

- `Recent Purchase Cash-Out Refi Prospects`
  Sarasota-focused workflow that targets:
  - purchases in the last 6 months
  - sale price over $250,000
  - no matching Sarasota mortgage found near the purchase date
- `Commercial Balloon Prospects`
  Merged balloon workflow that unions:
  - OCR-confirmed mortgage maturities due within 12 months with commercial debt signals
  - Sarasota commercial property with personal-name borrower, no current exemption, balloon maturity due within 6 months, and OCR note rate >= 8%

## Sarasota Cash-Out Refi Workflow

This is the most developed lead path in the app today.

1. Pull recent high-price sales from the Sarasota Property Appraiser export.
2. Keep sales inside the recent-purchase window and above the price threshold.
3. Search Sarasota Official Records for matching mortgage filings near the sale date.
4. If no matching mortgage is found, mark the lead as a cash-out refi prospect with `Mtg Amt At Purchase = 0`.
5. Save the results to CSV and show an outreach-first table in Streamlit.

Important implementation notes:

- Mortgage lookups are cached in `.cache/sarasota_mortgage_lookup.json`
- Owner-name search inputs are cleaned before being placed into Sarasota Clerk search fields
- The mortgage date window is tied to the sale date, not a generic year-long search

## Recommended Workflow

For fastest results:

1. Run lead generation with `Enable Skip Tracing` turned off.
2. Review the lead list first.
3. Turn skip tracing on only for smaller, higher-quality batches.

Why:

- Lead generation is now relatively fast.
- Google dorking is much slower and can hit rate limits.
- Skip-trace results are cached in `.cache/google_dork_cache.json`, so reruns improve over time.

## Project Structure

```text
OSINT-Skip-Tracing/
|-- app.py
|-- requirements.txt
|-- README.md
|-- scrapers/
|   |-- base_scraper.py
|   |-- sarasota_scraper.py
|   |-- miami_dade_scraper.py
|   `-- broward_scraper.py
|-- skip_tracing/
|   |-- google_dorking.py
|   `-- email_extractor.py
|-- utils/
|   |-- data_processor.py
|   `-- csv_exporter.py
|-- tests/
|   |-- test_base_scraper.py
|   |-- test_data_processor.py
|   `-- test_email_extractor.py
|-- .cache/
|   |-- sarasota_mortgage_lookup.json
|   `-- google_dork_cache.json
`-- exports/
    `-- prime_coastal_leads_*.csv
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Chromium

```bash
playwright install chromium
```

### 3. Run the app

```bash
streamlit run app.py
```

Default local URL:

```text
http://localhost:8501
```

## Sidebar Options

- `Florida Counties`
  Select one or more supported counties
- `Lead Type`
  Choose which lead strategy to run
- `Max Records per County`
  Soft cap for records returned
- `Headless Browser`
  Visible browser is usually safer for government portals
- `Enable Skip Tracing`
  Optional contact enrichment using Google dorking

## Output

Each successful run:

- displays results inside Streamlit
- saves a CSV to `exports/`
- keeps a simplified outreach-first table visible by default
- keeps the full wide dataset under `Full Detail View`

Common lead fields include:

- `Owner Name`
- `Property Address`
- `Mailing Address`
- `Last Sale Date`
- `Sale Price`
- `Mtg Amt At Purchase`
- `Mtg Amt Source`
- `Lead Strategy`
- `Lead Score`
- `Scraped Emails`

## Caching

Two caches are used to speed up reruns:

- `Sarasota mortgage lookup cache`
  Prevents repeated Sarasota Clerk mortgage searches for the same owner/date window
- `Google dork cache`
  Prevents repeated skip-trace lookups for the same owner name and preserves rate-limited outcomes

These caches live in `.cache/` and are ignored by git.

## Skip Tracing Behavior

Skip tracing uses Google dork queries plus lightweight page scraping.

Practical constraints:

- Google can return `429 Too Many Requests`
- when rate limiting is detected, the app now stops additional skip-trace queries and keeps partial results
- cached skip-trace outcomes make later reruns much faster

## Testing

Run the tests with:

```bash
pytest tests/ -v
```

## Extending the App

To add a new county scraper:

1. Create a new scraper in `scrapers/` that inherits from `BaseScraper`
2. Implement `county_name`, `search_url`, and `fetch_records(...)`
3. Register it in `COUNTY_SCRAPERS` inside `app.py`

Minimal example:

```python
from scrapers.base_scraper import BaseScraper


class PinellasScraper(BaseScraper):
    @property
    def county_name(self) -> str:
        return "Pinellas"

    @property
    def search_url(self) -> str:
        return "https://example.com"

    def fetch_records(self, lead_type, max_results=50):
        return []
```

## Notes

- This project uses public-record and open-web data only
- No paid APIs are required
- The app is intended to run locally
- Headful browser mode is usually the safest choice for county portals
