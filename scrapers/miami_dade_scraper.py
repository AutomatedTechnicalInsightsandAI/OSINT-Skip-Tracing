"""
Miami-Dade County Property Records scraper.

Targets:
  Clerk of Circuit Court: https://www2.miami-dadeclerk.com/officialrecords/
  Property Appraiser:     https://www.miamidade.gov/Apps/PA/propertysearch/

Miami-Dade exposes a public JSON API through its property-appraiser search
and an HTML table through the clerk official-records portal — both are
freely accessible without authentication.
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


class MiamiDadeScraper(BaseScraper):
    """Scraper for Miami-Dade County, FL."""

    CLERK_URL = "https://www2.miami-dadeclerk.com/officialrecords/"
    PA_SEARCH_URL = (
        "https://www.miamidade.gov/Apps/PA/propertysearch/#/"
    )
    PA_API_URL = (
        "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/"
        "PAPropertySearch_Public/FeatureServer/0/query"
    )

    @property
    def county_name(self) -> str:
        return "Miami-Dade"

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
        """Return property leads matching *lead_type* from Miami-Dade County."""
        logger.info(
            "Miami-Dade: fetching '%s' leads (max %d)", lead_type.value, max_results
        )

        if lead_type == LeadType.FLIPPER:
            return self._fetch_flippers(max_results)
        if lead_type == LeadType.HIGH_INTEREST:
            return self._fetch_high_interest(max_results)
        if lead_type == LeadType.PAST_FINANCING:
            return self._fetch_past_financing(max_results)
        return []

    # ------------------------------------------------------------------
    # Lead-type specific scrapers
    # ------------------------------------------------------------------

    def _clerk_search(self, page, instrument_type_filter: str, start_year: int = 2022):
        """
        Navigate the Miami-Dade Clerk advanced search and return parsed rows.

        Miami-Dade Clerk uses a web form at /officialrecords/ that accepts
        parameters for instrument type and date range.
        """
        page.goto(self.CLERK_URL, wait_until="domcontentloaded")
        self.sleep()
        self.random_scroll(page)

        # Fill the search form (selectors based on publicly-visible form ids)
        try:
            page.select_option(
                'select[name="InstrumentType"]', instrument_type_filter
            )
            page.fill('input[name="StartDate"]', f"01/01/{start_year}")
            page.fill('input[name="EndDate"]', f"12/31/{start_year + 1}")
            page.click('input[type="submit"]')
            page.wait_for_load_state("networkidle")
            self.sleep()
        except Exception as exc:
            logger.warning("Miami-Dade form interaction failed: %s", exc)

        return self.parse_html(page.content())

    def _parse_clerk_rows(self, soup) -> list[dict]:
        """Extract row data from the Miami-Dade clerk results table."""
        rows = []
        for tr in soup.select("table#SearchResults tr"):
            cells = tr.find_all("td")
            if len(cells) < 6:
                continue
            rows.append(
                {
                    "instrument_type": self.safe_text(cells[1]),
                    "grantor": self.safe_text(cells[2]),
                    "grantee": self.safe_text(cells[3]),
                    "rec_date": self.safe_text(cells[4]),
                    "book_page": self.safe_text(cells[5]),
                }
            )
        return rows

    def _fetch_flippers(self, max_results: int) -> List[PropertyRecord]:
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            soup = self._clerk_search(page, "WD")  # Warranty Deed
            rows = self._parse_clerk_rows(soup)

            # Group by grantor name as a proxy for parcel (Clerk lacks parcel col)
            grantor_transfers: dict[str, list[dict]] = {}
            for row in rows:
                grantor_transfers.setdefault(row["grantor"], []).append(row)

            for grantor, transfers in grantor_transfers.items():
                if len(records) >= max_results:
                    break
                if self.is_flipper(
                    [{"date": t["rec_date"]} for t in transfers]
                ):
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
            logger.error("Miami-Dade flipper scrape failed: %s", exc)

        logger.info("Miami-Dade flippers found: %d", len(records))
        return records

    def _fetch_high_interest(self, max_results: int) -> List[PropertyRecord]:
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            soup = self._clerk_search(page, "MT", start_year=2022)  # Mortgage
            rows = self._parse_clerk_rows(soup)

            for row in rows:
                if len(records) >= max_results:
                    break
                if not self.is_high_equity(row["rec_date"], row["instrument_type"]):
                    continue
                rec = PropertyRecord(
                    owner_name=row["grantee"],
                    last_sale_date=row["rec_date"],
                    estimated_interest_rate=estimate_interest_rate(row["rec_date"]),
                    deed_type=row["instrument_type"],
                    county=self.county_name,
                    lead_type=LeadType.HIGH_INTEREST.value,
                    notes="Peak-rate mortgage 2022-2023",
                )
                records.append(rec)
            page.context.close()
        except Exception as exc:
            logger.error("Miami-Dade high-interest scrape failed: %s", exc)

        logger.info("Miami-Dade high-interest found: %d", len(records))
        return records

    def _fetch_past_financing(self, max_results: int) -> List[PropertyRecord]:
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            # Search for Certificate of Title (CT) and Satisfaction of Mortgage (SM)
            for code in ("CT", "SM"):
                if len(records) >= max_results:
                    break
                soup = self._clerk_search(page, code, start_year=2020)
                rows = self._parse_clerk_rows(soup)
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
            logger.error("Miami-Dade past-financing scrape failed: %s", exc)

        logger.info("Miami-Dade past-financing found: %d", len(records))
        return records
