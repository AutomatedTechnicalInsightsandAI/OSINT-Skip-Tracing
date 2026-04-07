# OSINT Skip-Tracing — Prime Coastal Funding Lead Generator

A local Python web application (Streamlit) that generates **commercial real
estate leads** for Prime Coastal Funding by scraping free Florida public
property records and enriching them with open-source skip-traced contact
information — **no paid APIs required**.

---

## Features

| Module | Description |
|--------|-------------|
| **Base Scraper** | Abstract class with Playwright headful browser, random-sleep anti-detection, and BeautifulSoup parsing helpers |
| **County Scrapers** | Concrete scrapers for **Sarasota**, **Miami-Dade**, and **Broward** counties — easily extendable to additional counties |
| **Skip Tracing** | Google Dorking (via `googlesearch-python`) + `re`-based email extraction from page source |
| **Streamlit Dashboard** | Sidebar lead-type selector, county multi-select, real-time progress, metrics, and one-click CSV download |

### Lead Types

* **Fix & Flip Investors** — Properties with ≥ 2 deed transfers within 12 months
* **High Interest / High Equity (DSCR Prospects)** — Mortgage Deeds from 2022-2023 (peak rate era) or properties with no mortgage in 20+ years
* **Past Financing** — Certificate of Title or Satisfaction of Mortgage records

### CSV Output Columns

```
Owner Name | Property Address | Mailing Address | Last Sale Date | Estimated Interest Rate | Scraped Emails
```

---

## Project Structure

```
OSINT-Skip-Tracing/
├── app.py                        # Streamlit dashboard entry point
├── requirements.txt
├── scrapers/
│   ├── base_scraper.py           # Abstract base class + shared utilities
│   ├── sarasota_scraper.py       # Sarasota County scraper
│   ├── miami_dade_scraper.py     # Miami-Dade County scraper
│   └── broward_scraper.py        # Broward County scraper
├── skip_tracing/
│   ├── google_dorking.py         # Google Dork query engine
│   └── email_extractor.py        # Regex email extractor (re library)
├── utils/
│   ├── data_processor.py         # Record merging + skip-trace enrichment
│   └── csv_exporter.py           # CSV serialisation helpers
└── tests/
    ├── test_base_scraper.py
    ├── test_email_extractor.py
    └── test_data_processor.py
```

---

## Setup & Usage

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright browsers (first run only)

```bash
playwright install chromium
```

### 3. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501** — no login required.

---

## Sidebar Controls

| Control | Description |
|---------|-------------|
| **Florida Counties** | Multi-select: Sarasota, Miami-Dade, Broward |
| **Lead Type** | Fix & Flip / High Interest / Past Financing |
| **Max Records per County** | Soft cap (5–200, default 50) |
| **Headless Browser** | Uncheck for headful mode (recommended for government sites) |
| **Enable Skip Tracing** | Run Google Dork queries to find owner emails (slow) |

---

## Extending to New Counties

Create a new file in `scrapers/` that inherits from `BaseScraper`:

```python
from scrapers.base_scraper import BaseScraper, LeadType, PropertyRecord

class PinellasScraper(BaseScraper):
    @property
    def county_name(self) -> str:
        return "Pinellas"

    @property
    def search_url(self) -> str:
        return "https://www.pinellasclerk.org/asp/officialrecords.asp"

    def fetch_records(self, lead_type, max_results=50):
        ...  # county-specific scraping logic
```

Then register it in `app.py`:

```python
COUNTY_SCRAPERS["Pinellas"] = PinellasScraper
```

---

## Anti-Detection Measures

* **Headful browser mode** (default) — opens a visible Chromium window, which is far less likely to be fingerprinted as a bot by government portals
* **Random sleep intervals** — 2–6 s between page requests, 5–12 s on heavy pages
* **Random user-agent rotation** via `fake-useragent`
* **Random scroll simulation** to mimic human reading behaviour

---

## Constraints & Compliance

* **No paid APIs** — uses only `pandas`, `playwright`, `streamlit`, `beautifulsoup4`, `googlesearch-python`, `requests`, and `fake-useragent`
* **Public records only** — all data sourced from freely accessible Florida government portals
* **Local only** — the app runs on `localhost` with no authentication

---

## Running Tests

```bash
pytest tests/ -v
```
