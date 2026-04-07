"""
Broward County Property Records scraper.

Targets:
  Clerk of Courts:     https://www.browardclerk.org/Web2/
  Property Appraiser:  https://bcpa.net/

Broward Clerk exposes a public Official Records search through their
"Web2" portal and the BCPA provides a name/address search without auth.
"""

from __future__ import annotations

import logging
from typing import List

from scrapers.base_scraper import (
    BaseScraper,
    LeadType,
    PropertyRecord,
    estimate_interest_rate,
)

logger = logging.getLogger(__name__)


class BrowardScraper(BaseScraper):
    """Scraper for Broward County, FL."""

    CLERK_URL = "https://www.browardclerk.org/Web2/"
    PA_URL = "https://bcpa.net/RecAcctSearch.asp"

    @property
    def county_name(self) -> str:
        return "Broward"

    @property
    def search_url(self) -> str:
        return self.CLERK_URL

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_records(
        self,
        lead_type: LeadType,
        max_results: int = 50,
    ) -> List[PropertyRecord]:
        """Return property leads matching *lead_type* from Broward County."""
        logger.info(
            "Broward: fetching '%s' leads (max %d)", lead_type.value, max_results
        )

        if lead_type == LeadType.FLIPPER:
            return self._fetch_flippers(max_results)
        if lead_type == LeadType.HIGH_INTEREST:
            return self._fetch_high_interest(max_results)
        if lead_type == LeadType.PAST_FINANCING:
            return self._fetch_past_financing(max_results)
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_clerk_search(self, page):
        """Navigate to the Broward Clerk Official Records search page."""
        page.goto(self.CLERK_URL, wait_until="domcontentloaded")
        self.sleep()
        self.random_scroll(page)

    def _clerk_instrument_search(
        self,
        page,
        instrument_code: str,
        date_from: str = "01/01/2022",
        date_to: str = "12/31/2023",
    ):
        """
        Perform an instrument-type search on the Broward Clerk portal.

        Broward's Web2 portal uses GET parameters for the official-records
        search: ?InstrumentType=WD&DateFrom=01/01/2022&DateTo=12/31/2023
        """
        url = (
            f"{self.CLERK_URL}OfficialRecords/Details/InstrumentSearch"
            f"?InstrumentType={instrument_code}"
            f"&DateFrom={date_from}&DateTo={date_to}"
        )
        try:
            page.goto(url, wait_until="networkidle")
            self.sleep()
            self.random_scroll(page)
        except Exception as exc:
            logger.warning("Broward clerk navigation failed: %s", exc)
        return self.parse_html(page.content())

    def _parse_broward_rows(self, soup) -> list[dict]:
        """Parse the Broward clerk result table (tbody rows)."""
        rows = []
        for tr in soup.select("table#tblResults tbody tr"):
            cells = tr.find_all("td")
            if len(cells) < 5:
                continue
            rows.append(
                {
                    "instrument_type": self.safe_text(cells[0]),
                    "rec_date": self.safe_text(cells[1]),
                    "grantor": self.safe_text(cells[2]),
                    "grantee": self.safe_text(cells[3]),
                    "legal_desc": self.safe_text(cells[4]),
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Lead-type fetchers
    # ------------------------------------------------------------------

    def _fetch_flippers(self, max_results: int) -> List[PropertyRecord]:
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            self._open_clerk_search(page)

            soup = self._clerk_instrument_search(
                page, "WD", "01/01/2023", "12/31/2024"
            )
            rows = self._parse_broward_rows(soup)

            # Group by grantor (proxy for property/seller identity)
            grantor_map: dict[str, list[dict]] = {}
            for row in rows:
                grantor_map.setdefault(row["grantor"], []).append(row)

            for grantor, transfers in grantor_map.items():
                if len(records) >= max_results:
                    break
                if self.is_flipper([{"date": t["rec_date"]} for t in transfers]):
                    last = transfers[-1]
                    rec = PropertyRecord(
                        owner_name=last["grantee"],
                        last_sale_date=last["rec_date"],
                        estimated_interest_rate=estimate_interest_rate(
                            last["rec_date"]
                        ),
                        deed_type=last["instrument_type"],
                        county=self.county_name,
                        lead_type=LeadType.FLIPPER.value,
                        notes="2+ transfers within 12 months",
                    )
                    records.append(rec)
            page.context.close()
        except Exception as exc:
            logger.error("Broward flipper scrape failed: %s", exc)

        logger.info("Broward flippers found: %d", len(records))
        return records

    def _fetch_high_interest(self, max_results: int) -> List[PropertyRecord]:
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            self._open_clerk_search(page)

            for year_range in [("01/01/2022", "12/31/2022"), ("01/01/2023", "12/31/2023")]:
                if len(records) >= max_results:
                    break
                soup = self._clerk_instrument_search(page, "MT", *year_range)
                rows = self._parse_broward_rows(soup)

                for row in rows:
                    if len(records) >= max_results:
                        break
                    if not self.is_high_equity(row["rec_date"], row["instrument_type"]):
                        continue
                    rec = PropertyRecord(
                        owner_name=row["grantee"],
                        last_sale_date=row["rec_date"],
                        estimated_interest_rate=estimate_interest_rate(
                            row["rec_date"]
                        ),
                        deed_type=row["instrument_type"],
                        county=self.county_name,
                        lead_type=LeadType.HIGH_INTEREST.value,
                        notes="Peak-rate mortgage 2022-2023",
                    )
                    records.append(rec)
            page.context.close()
        except Exception as exc:
            logger.error("Broward high-interest scrape failed: %s", exc)

        logger.info("Broward high-interest found: %d", len(records))
        return records

    def _fetch_past_financing(self, max_results: int) -> List[PropertyRecord]:
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            self._open_clerk_search(page)

            for code in ("CT", "SM"):
                if len(records) >= max_results:
                    break
                soup = self._clerk_instrument_search(
                    page, code, "01/01/2020", "12/31/2024"
                )
                rows = self._parse_broward_rows(soup)
                for row in rows:
                    if len(records) >= max_results:
                        break
                    rec = PropertyRecord(
                        owner_name=row["grantee"],
                        last_sale_date=row["rec_date"],
                        estimated_interest_rate=estimate_interest_rate(
                            row["rec_date"]
                        ),
                        deed_type=row["instrument_type"],
                        county=self.county_name,
                        lead_type=LeadType.PAST_FINANCING.value,
                    )
                    records.append(rec)
            page.context.close()
        except Exception as exc:
            logger.error("Broward past-financing scrape failed: %s", exc)

        logger.info("Broward past-financing found: %d", len(records))
        return records
