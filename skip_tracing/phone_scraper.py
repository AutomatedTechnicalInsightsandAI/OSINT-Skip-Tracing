"""
Phone number scraper for skip tracing.

Strategy (no paid API required):
  1. Google Dork queries targeting public sources (whitepages, spokeo, etc.)
  2. Regex extraction of E.164 / NANP phone numbers from scraped page HTML
  3. Results cached to .cache/phone_cache.json to avoid redundant lookups

For LLC owners the address is included in the query to improve accuracy.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from pathlib import Path
from typing import List, Optional

import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phone regex — matches US numbers in a wide variety of formats
# ---------------------------------------------------------------------------

_PHONE_PATTERN = re.compile(
    r"""
    (?<!\d)                        # not preceded by digit
    (?:\+?1[\s.\-]?)?              # optional country code
    \(?([2-9]\d{2})\)?             # area code (NPA)
    [\s.\-]?
    ([2-9]\d{2})                   # exchange (NXX)
    [\s.\-]?
    (\d{4})                        # subscriber number
    (?!\d)                         # not followed by digit
    """,
    re.VERBOSE,
)

# Dork templates — {name} and optionally {address}
_PHONE_DORKS = [
    '"{name}" phone number site:whitepages.com',
    '"{name}" "{city}" phone contact',
    '"{name}" phone Florida real estate owner',
    '"{name}" contact number site:spokeo.com',
    '"{name}" "{state}" phone',
]

_SEARCH_PAUSE_RANGE = (8.0, 20.0)
_FETCH_PAUSE_RANGE = (2.0, 5.0)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Known bogus / test numbers to exclude
_EXCLUDED_NUMBERS = frozenset(
    {"8005551212", "5555555555", "0000000000", "1234567890"}
)


def _normalize_phone(match: re.Match) -> str:
    """Return a consistently formatted phone string: (NPA) NXX-XXXX."""
    area, exchange, subscriber = match.group(1), match.group(2), match.group(3)
    return f"({area}) {exchange}-{subscriber}"


class PhoneScraper:
    """
    Google Dork-based phone number lookup for a given owner name + address.

    Parameters
    ----------
    max_results_per_query:
        Number of Google search results to retrieve per dork query.
    fetch_pages:
        Whether to follow result URLs and scrape the page for phone numbers.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        max_results_per_query: int = 5,
        fetch_pages: bool = True,
        timeout: int = 10,
    ):
        self.max_results_per_query = max_results_per_query
        self.fetch_pages = fetch_pages
        self.timeout = timeout
        self._cache_path = Path(".cache") / "phone_cache.json"
        self._cache = self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(
        self,
        owner_name: str,
        mailing_address: str = "",
    ) -> dict:
        """
        Return phone numbers found for *owner_name*.

        Parameters
        ----------
        owner_name:
            Full name of the owner / LLC.
        mailing_address:
            Optional mailing address — used to refine dork queries.

        Returns
        -------
        dict with keys:
            ``phones``       – sorted, de-duplicated list of phone strings
            ``cached``       – True if result came from local cache
            ``rate_limited`` – True if Google throttled the session
        """
        name = (owner_name or "").strip()
        if not name:
            return {"phones": [], "cached": False, "rate_limited": False}

        cache_key = f"{name}|{mailing_address}"
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            return {
                "phones": entry.get("phones", []),
                "cached": True,
                "rate_limited": entry.get("rate_limited", False),
            }

        # Parse city / state out of the address for richer queries
        city, state = self._parse_city_state(mailing_address)

        phones: set[str] = set()
        rate_limited = False

        for template in _PHONE_DORKS:
            query = template.format(name=name, city=city or "FL", state=state or "Florida")
            found, was_rate_limited = self._run_query(query)
            phones.update(found)
            if was_rate_limited:
                rate_limited = True
                break
            self._pause()

        result_phones = sorted(phones)
        self._cache[cache_key] = {
            "phones": result_phones,
            "rate_limited": rate_limited,
        }
        self._save_cache()

        return {
            "phones": result_phones,
            "cached": False,
            "rate_limited": rate_limited,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_query(self, query: str) -> tuple[list[str], bool]:
        phones: list[str] = []
        rate_limited = False

        try:
            from googlesearch import search as google_search  # noqa: PLC0415

            urls = list(
                google_search(
                    query,
                    num_results=self.max_results_per_query,
                    lang="en",
                    sleep_interval=random.uniform(2, 5),
                )
            )
        except Exception as exc:
            logger.warning("Google search failed for '%s': %s", query, exc)
            if "429" in repr(exc) or "Too Many Requests" in repr(exc):
                rate_limited = True
            return phones, rate_limited

        if self.fetch_pages:
            for url in urls:
                page_phones = self._scrape_url_for_phones(url)
                phones.extend(page_phones)
                self._fetch_pause()

        return phones, rate_limited

    def _scrape_url_for_phones(self, url: str) -> List[str]:
        """GET *url* and extract phone numbers from the response."""
        try:
            resp = requests.get(
                url, headers=_HEADERS, timeout=self.timeout, allow_redirects=True
            )
            resp.raise_for_status()
            return self._extract_phones(resp.text)
        except Exception as exc:
            logger.debug("Could not fetch %s: %s", url, exc)
            return []

    @staticmethod
    def _extract_phones(text: str) -> List[str]:
        """Return de-duplicated, normalized phone numbers from *text*."""
        found = []
        seen: set[str] = set()
        for m in _PHONE_PATTERN.finditer(text):
            raw = f"{m.group(1)}{m.group(2)}{m.group(3)}"
            if raw in _EXCLUDED_NUMBERS:
                continue
            normalized = _normalize_phone(m)
            if normalized not in seen:
                seen.add(normalized)
                found.append(normalized)
        return found

    @staticmethod
    def _parse_city_state(address: str) -> tuple[str, str]:
        """Best-effort city/state extraction from a US mailing address string."""
        # Typical format: "123 MAIN ST, MIAMI, FL 33101"
        parts = [p.strip() for p in address.split(",")]
        city = parts[1] if len(parts) >= 2 else ""
        state_zip = parts[2].split() if len(parts) >= 3 else []
        state = state_zip[0] if state_zip else ""
        return city, state

    @staticmethod
    def _pause() -> None:
        delay = random.uniform(*_SEARCH_PAUSE_RANGE)
        logger.debug("Phone scraper pause: %.1f s", delay)
        time.sleep(delay)

    @staticmethod
    def _fetch_pause() -> None:
        time.sleep(random.uniform(*_FETCH_PAUSE_RANGE))

    def _load_cache(self) -> dict:
        try:
            if not self._cache_path.exists():
                return {}
            with self._cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning("Could not load phone cache: %s", exc)
            return {}

    def _save_cache(self) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, sort_keys=True)
            tmp.replace(self._cache_path)
        except Exception as exc:
            logger.warning("Could not save phone cache: %s", exc)
