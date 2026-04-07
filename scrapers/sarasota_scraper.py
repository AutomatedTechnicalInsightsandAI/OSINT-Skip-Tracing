"""
Sarasota County Property Records scraper.

Targets:
  Clerk of Circuit Court: https://www.sarasotaclerk.com/
  Property Appraiser:     https://www.sc-pa.com/

Sarasota uses the Fidlar/iDoc recording search for Official Records
and a standard address/parcel search for property-appraiser data.
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


class SarasotaScraper(BaseScraper):
    """Scraper for Sarasota County, FL."""

    CLERK_URL = "https://www.sarasotaclerk.com/official-records/"
    PA_URL = "https://www.sc-pa.com/propertysearch/find"

    @property
    def county_name(self) -> str:
        return "Sarasota"

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
        """Return property leads matching *lead_type* from Sarasota County."""
        logger.info(
            "Sarasota: fetching '%s' leads (max %d)", lead_type.value, max_results
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

    def _fetch_flippers(self, max_results: int) -> List[PropertyRecord]:
        """
        Identify properties with ≥2 deed transfers within 12 months by
        searching the Official Records for 'Warranty Deed' instrument type
        and grouping by parcel.
        """
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            page.goto(self.CLERK_URL, wait_until="domcontentloaded")
            self.sleep()
            self.random_scroll(page)

            # Navigate to the Official Records search form
            page.goto(
                "https://www.sarasotaclerk.com/official-records/",
                wait_until="networkidle",
            )
            self.sleep()

            html = page.content()
            soup = self.parse_html(html)

            # Parse deed records from the results table (site-specific selectors)
            deed_rows = soup.select("table.results-table tr")
            parcel_transfers: dict[str, list[dict]] = {}

            for row in deed_rows:
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                instrument_type = self.safe_text(cells[1])
                if "deed" not in instrument_type.lower():
                    continue

                grantor = self.safe_text(cells[2])
                grantee = self.safe_text(cells[3])
                rec_date = self.safe_text(cells[4])
                parcel_id = self.safe_text(cells[5]) if len(cells) > 5 else ""

                parcel_transfers.setdefault(parcel_id, []).append(
                    {
                        "date": rec_date,
                        "grantor": grantor,
                        "grantee": grantee,
                        "deed_type": instrument_type,
                    }
                )

            for parcel_id, transfers in parcel_transfers.items():
                if len(records) >= max_results:
                    break
                if self.is_flipper(transfers):
                    last = transfers[-1]
                    rec = PropertyRecord(
                        owner_name=last.get("grantee", ""),
                        parcel_id=parcel_id,
                        last_sale_date=last.get("date", ""),
                        estimated_interest_rate=estimate_interest_rate(
                            last.get("date", "")
                        ),
                        deed_type=last.get("deed_type", ""),
                        county=self.county_name,
                        lead_type=LeadType.FLIPPER.value,
                        notes="2+ transfers within 12 months",
                    )
                    records.append(rec)

            page.context.close()
        except Exception as exc:
            logger.error("Sarasota flipper scrape failed: %s", exc)

        logger.info("Sarasota flippers found: %d", len(records))
        return records

    def _fetch_high_interest(self, max_results: int) -> List[PropertyRecord]:
        """
        Search for Mortgage Deeds recorded in 2022-2023 (peak rates) or
        properties with no mortgage recorded in the last 20 years.
        """
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            # Search clerk records for Mortgage Deeds
            page.goto(self.CLERK_URL, wait_until="domcontentloaded")
            self.sleep()

            html = page.content()
            soup = self.parse_html(html)

            rows = soup.select("table.results-table tr")
            for row in rows:
                if len(records) >= max_results:
                    break
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                instrument_type = self.safe_text(cells[1])
                rec_date = self.safe_text(cells[4])

                if not self.is_high_equity(rec_date, instrument_type):
                    continue

                rec = PropertyRecord(
                    owner_name=self.safe_text(cells[3]),
                    last_sale_date=rec_date,
                    estimated_interest_rate=estimate_interest_rate(rec_date),
                    deed_type=instrument_type,
                    county=self.county_name,
                    lead_type=LeadType.HIGH_INTEREST.value,
                    notes="Peak-rate mortgage or no mortgage >20 years",
                )
                records.append(rec)

            page.context.close()
        except Exception as exc:
            logger.error("Sarasota high-interest scrape failed: %s", exc)

        logger.info("Sarasota high-interest found: %d", len(records))
        return records

    def _fetch_past_financing(self, max_results: int) -> List[PropertyRecord]:
        """
        Search for Certificate of Title or Satisfaction of Mortgage instruments.
        """
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()
            page.goto(self.CLERK_URL, wait_until="domcontentloaded")
            self.sleep()

            html = page.content()
            soup = self.parse_html(html)

            rows = soup.select("table.results-table tr")
            for row in rows:
                if len(records) >= max_results:
                    break
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                instrument_type = self.safe_text(cells[1])

                if not self.is_past_financing(instrument_type):
                    continue

                rec_date = self.safe_text(cells[4])
                rec = PropertyRecord(
                    owner_name=self.safe_text(cells[3]),
                    last_sale_date=rec_date,
                    estimated_interest_rate=estimate_interest_rate(rec_date),
                    deed_type=instrument_type,
                    county=self.county_name,
                    lead_type=LeadType.PAST_FINANCING.value,
                )
                records.append(rec)

            page.context.close()
        except Exception as exc:
            logger.error("Sarasota past-financing scrape failed: %s", exc)

        logger.info("Sarasota past-financing found: %d", len(records))
        return records
