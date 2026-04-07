"""
Google Dorking-based skip tracer.

Uses ``googlesearch-python`` to fire targeted search queries that attempt
to surface public email addresses and LinkedIn profiles for a given owner
name without any paid API.

IMPORTANT — ethical usage note
-------------------------------
This module only queries publicly-indexed information.  It introduces
mandatory random sleep intervals to stay within the spirit of Google's
public search usage guidelines and avoid rate-limiting.  Do NOT remove
the sleep calls or run this at high concurrency.
"""

from __future__ import annotations

import logging
import random
import re
import time
from typing import List, Optional

import requests
from urllib.parse import urlparse
from skip_tracing.email_extractor import EmailExtractor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dork template library
# ---------------------------------------------------------------------------

_EMAIL_DORKS = [
    '"{name}" email site:linkedin.com',
    '"{name}" "@gmail.com" OR "@yahoo.com" OR "@outlook.com"',
    '"{name}" contact email Florida real estate',
    '"{name}" email investor Florida',
]

_LINKEDIN_DORKS = [
    'site:linkedin.com/in "{name}" Florida',
    'site:linkedin.com "{name}" real estate Florida',
]

# Pause between consecutive Google queries (seconds)
_SEARCH_PAUSE_RANGE = (8.0, 20.0)

# Pause between page-fetch requests (seconds)
_FETCH_PAUSE_RANGE = (2.0, 5.0)

# Default HTTP request headers to look like a browser
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class GoogleDorker:
    """
    Fire Google Dork queries and collect email addresses for a given owner.

    Parameters
    ----------
    max_results_per_query:
        Number of Google search results to retrieve per dork query.
    fetch_pages:
        Whether to follow result URLs and scrape the page source for emails.
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
        self._extractor = EmailExtractor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, owner_name: str) -> dict:
        """
        Run all dork templates for *owner_name* and return aggregated results.

        Returns
        -------
        dict with keys:
            ``emails``   – sorted list of discovered email addresses
            ``linkedin``  – list of LinkedIn profile URLs found
            ``queries``   – list of queries that were executed
        """
        if not owner_name or not owner_name.strip():
            return {"emails": [], "linkedin": [], "queries": []}

        name = owner_name.strip()
        emails: set[str] = set()
        linkedin_urls: list[str] = []
        executed_queries: list[str] = []

        # Email dorks
        for template in _EMAIL_DORKS:
            query = template.format(name=name)
            found_emails, _ = self._run_query(query)
            emails.update(found_emails)
            executed_queries.append(query)
            self._pause()

        # LinkedIn dorks
        for template in _LINKEDIN_DORKS:
            query = template.format(name=name)
            _, found_linkedin = self._run_query(query, linkedin_mode=True)
            linkedin_urls.extend(found_linkedin)
            executed_queries.append(query)
            self._pause()

        return {
            "emails": sorted(emails),
            "linkedin": list(dict.fromkeys(linkedin_urls)),  # dedup, preserve order
            "queries": executed_queries,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_query(
        self, query: str, linkedin_mode: bool = False
    ) -> tuple[list[str], list[str]]:
        """
        Execute a single Google search query and return (emails, linkedin_urls).
        """
        emails: list[str] = []
        linkedin_urls: list[str] = []

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
            return emails, linkedin_urls

        for url in urls:
            try:
                parsed = urlparse(url)
                # Use the registered domain (netloc) to avoid substring ambiguity
                netloc = parsed.netloc.lower().lstrip("www.")
                if netloc == "linkedin.com" or netloc.endswith(".linkedin.com"):
                    linkedin_urls.append(url)
            except Exception:
                pass

            if self.fetch_pages:
                page_emails = self._scrape_url_for_emails(url)
                emails.extend(page_emails)
                self._fetch_pause()

        return emails, linkedin_urls

    def _scrape_url_for_emails(self, url: str) -> List[str]:
        """GET *url* and extract email addresses from the response text."""
        try:
            resp = requests.get(
                url,
                headers=_HEADERS,
                timeout=self.timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return self._extractor.extract(resp.text)
        except Exception as exc:
            logger.debug("Could not fetch %s: %s", url, exc)
            return []

    @staticmethod
    def _pause() -> None:
        """Sleep between search queries to respect rate limits."""
        delay = random.uniform(*_SEARCH_PAUSE_RANGE)
        logger.debug("Google dork pause: %.1f s", delay)
        time.sleep(delay)

    @staticmethod
    def _fetch_pause() -> None:
        """Shorter sleep between page-fetch requests."""
        delay = random.uniform(*_FETCH_PAUSE_RANGE)
        time.sleep(delay)
