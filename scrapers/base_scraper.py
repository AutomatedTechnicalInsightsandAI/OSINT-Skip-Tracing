"""
Base scraper class for Florida county property records.

Provides a common interface and shared utilities (Playwright headful browser,
random sleep anti-detection, BeautifulSoup parsing) that county-specific
scrapers can extend.
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LeadType(str, Enum):
    """Supported lead categories for Prime Coastal Funding."""

    FLIPPER = "Fix & Flip Investors"
    HIGH_INTEREST = "High Interest / High Equity (DSCR Prospects)"
    PAST_FINANCING = "Past Financing (Satisfied Mortgage / Certificate of Title)"


@dataclass
class PropertyRecord:
    """Normalized property record produced by any county scraper."""

    owner_name: str = ""
    property_address: str = ""
    mailing_address: str = ""
    last_sale_date: str = ""
    estimated_interest_rate: str = ""
    scraped_emails: str = ""
    county: str = ""
    lead_type: str = ""
    # Additional metadata — not in the required CSV columns but useful for UX
    parcel_id: str = ""
    deed_type: str = ""
    sale_price: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        """Return only the required CSV columns plus optional extras."""
        return {
            "Owner Name": self.owner_name,
            "Property Address": self.property_address,
            "Mailing Address": self.mailing_address,
            "Last Sale Date": self.last_sale_date,
            "Estimated Interest Rate": self.estimated_interest_rate,
            "Scraped Emails": self.scraped_emails,
            "County": self.county,
            "Lead Type": self.lead_type,
            "Parcel ID": self.parcel_id,
            "Deed Type": self.deed_type,
            "Sale Price": self.sale_price,
            "Notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Rate estimation helpers
# ---------------------------------------------------------------------------

# Approximate 30-year fixed mortgage rate benchmarks by year (US national avg)
_RATE_BENCHMARKS: dict[int, float] = {
    2018: 4.54,
    2019: 3.94,
    2020: 3.11,
    2021: 2.96,
    2022: 5.34,
    2023: 6.81,
    2024: 6.72,
    2025: 6.65,
}


def estimate_interest_rate(date_str: str) -> str:
    """
    Return an estimated 30-yr fixed mortgage rate for a given deed date.

    The estimate is based on national annual averages.  If the year is not in
    the benchmark table the closest year is used.
    """
    if not date_str:
        return "Unknown"
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            year = dt.year
            if year in _RATE_BENCHMARKS:
                return f"~{_RATE_BENCHMARKS[year]:.2f}%"
            # Closest year
            closest = min(_RATE_BENCHMARKS.keys(), key=lambda y: abs(y - year))
            return f"~{_RATE_BENCHMARKS[closest]:.2f}% (est. from {closest})"
        except ValueError:
            continue
    return "Unknown"


def is_high_rate_era(date_str: str) -> bool:
    """Return True if deed date falls in 2022-2023 (peak rate period)."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.year in (2022, 2023)
        except ValueError:
            continue
    return False


def is_older_than_years(date_str: str, years: int = 20) -> bool:
    """Return True if the date is older than *years* from today."""
    cutoff = datetime.now() - timedelta(days=years * 365)
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt < cutoff
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------


class BaseScraper(ABC):
    """
    Abstract base class for Florida county property-record scrapers.

    Subclasses must implement:
        * ``county_name`` property
        * ``search_url`` property
        * ``fetch_records(lead_type, max_results)`` method

    The base class provides:
        * Playwright browser management (headful, to avoid bot detection)
        * BeautifulSoup parsing helpers
        * Random sleep / anti-detection utilities
        * Lead-type filtering logic
    """

    # Sleep range in seconds between page requests (min, max)
    SLEEP_RANGE: tuple[float, float] = (2.0, 6.0)
    # Additional jitter added on heavy pages
    HEAVY_SLEEP_RANGE: tuple[float, float] = (5.0, 12.0)

    def __init__(self, headless: bool = False, timeout_ms: int = 30_000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._browser = None
        self._playwright = None

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def county_name(self) -> str:
        """Human-readable county name, e.g. 'Sarasota'."""

    @property
    @abstractmethod
    def search_url(self) -> str:
        """Entry-point URL for the county property-search portal."""

    @abstractmethod
    def fetch_records(
        self,
        lead_type: LeadType,
        max_results: int = 50,
    ) -> List[PropertyRecord]:
        """
        Scrape and return a list of *PropertyRecord* objects.

        Parameters
        ----------
        lead_type:
            Which category of leads to fetch.
        max_results:
            Soft cap on the number of records to return.
        """

    # ------------------------------------------------------------------
    # Browser lifecycle (Playwright)
    # ------------------------------------------------------------------

    def start_browser(self):
        """Launch a Playwright Chromium browser (headful by default)."""
        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            logger.info("Browser launched (headless=%s)", self.headless)
        except Exception as exc:
            logger.error("Failed to launch browser: %s", exc)
            raise

    def new_page(self):
        """Return a new browser page with a randomised user-agent."""
        if self._browser is None:
            self.start_browser()
        try:
            from fake_useragent import UserAgent  # noqa: PLC0415

            ua = UserAgent()
            user_agent = ua.random
        except Exception:
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        context = self._browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = context.new_page()
        page.set_default_timeout(self.timeout_ms)
        return page

    def close_browser(self):
        """Shut down the Playwright browser and its sub-processes."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.info("Browser closed.")

    def __enter__(self):
        self.start_browser()
        return self

    def __exit__(self, *_):
        self.close_browser()

    # ------------------------------------------------------------------
    # Anti-detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def sleep(heavy: bool = False) -> None:
        """Sleep for a random interval to mimic human behaviour."""
        lo, hi = (
            BaseScraper.HEAVY_SLEEP_RANGE if heavy else BaseScraper.SLEEP_RANGE
        )
        delay = random.uniform(lo, hi)
        logger.debug("Sleeping %.2f s", delay)
        time.sleep(delay)

    @staticmethod
    def random_scroll(page) -> None:
        """Scroll the page by a random amount to simulate reading."""
        scroll_y = random.randint(300, 900)
        page.evaluate(f"window.scrollBy(0, {scroll_y})")
        time.sleep(random.uniform(0.3, 1.2))

    # ------------------------------------------------------------------
    # HTML parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        """Parse raw HTML with lxml (fallback to html.parser)."""
        try:
            return BeautifulSoup(html, "lxml")
        except Exception:
            return BeautifulSoup(html, "html.parser")

    @staticmethod
    def safe_text(element) -> str:
        """Extract stripped text from a BeautifulSoup element or return ''."""
        if element is None:
            return ""
        return element.get_text(separator=" ", strip=True)

    # ------------------------------------------------------------------
    # Lead filtering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_flipper(transfers: list[dict]) -> bool:
        """
        Return True if *transfers* contains ≥2 transactions within 12 months.

        Each transfer dict must have a ``date`` key with a parseable date string.
        """
        dates: list[datetime] = []
        for t in transfers:
            raw = t.get("date", "")
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y"):
                try:
                    dates.append(datetime.strptime(raw.strip(), fmt))
                    break
                except ValueError:
                    continue

        if len(dates) < 2:
            return False

        dates.sort()
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]) <= timedelta(days=365):
                return True
        return False

    @staticmethod
    def is_high_equity(deed_date: str, deed_type: str) -> bool:
        """
        Return True for peak-rate mortgages (2022-2023) or
        properties with no recorded mortgage in the last 20 years.
        """
        no_recent_mortgage = deed_type.lower() in (
            "warranty deed",
            "quit claim deed",
            "special warranty deed",
        ) and is_older_than_years(deed_date, 20)
        peak_rate_mortgage = (
            "mortgage" in deed_type.lower() and is_high_rate_era(deed_date)
        )
        return no_recent_mortgage or peak_rate_mortgage

    @staticmethod
    def is_past_financing(deed_type: str) -> bool:
        """Return True for Certificate of Title or Satisfaction of Mortgage."""
        dt_lower = deed_type.lower()
        return "certificate of title" in dt_lower or "satisfaction" in dt_lower
