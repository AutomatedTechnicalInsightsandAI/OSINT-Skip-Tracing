"""
Sarasota County Property Records scraper.

Targets:
  Clerk of Circuit Court: https://secure.sarasotaclerk.com/OfficialRecords.aspx
  Property Appraiser:     https://www.sc-pa.com/

Sarasota uses an ASP.NET WebForms Official Records search portal.
Playwright is used to fill in and submit the search form before parsing
the GridView results table.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
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

    # Bug 1 fix: use the correct ASP.NET search portal URL.
    CLERK_URL = "https://secure.sarasotaclerk.com/OfficialRecords.aspx"
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
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_official_records(
        self,
        page,
        doc_type: str,
        date_from: str,
        date_to: str,
    ) -> None:
        """
        Navigate to the Sarasota ASP.NET Official Records portal and submit a
        search for *doc_type* within the given date range.

        Bug 3 fix: actually fill in and submit the search form instead of just
        reading the landing page HTML.
        """
        page.goto(self.CLERK_URL, wait_until="domcontentloaded")
        self.sleep()
        self.random_scroll(page)

        try:
            # Select document/instrument type
            page.select_option("select[id*='DocType']", label=doc_type)
        except Exception:
            # Fall back to any visible doc-type dropdown if the ID varies
            try:
                page.select_option("select", label=doc_type)
            except Exception as exc:
                logger.warning(
                    "Sarasota: could not select doc type '%s': %s",
                    doc_type,
                    repr(exc),
                )

        try:
            # Fill start date
            page.fill("input[id*='DateFrom']", date_from)
        except Exception as exc:
            logger.warning("Sarasota: could not fill DateFrom: %s", repr(exc))

        try:
            # Fill end date
            page.fill("input[id*='DateTo']", date_to)
        except Exception as exc:
            logger.warning("Sarasota: could not fill DateTo: %s", repr(exc))

        try:
            # Click the Search / Submit button
            page.click("input[type='submit'], button[type='submit']")
            page.wait_for_load_state("networkidle")
            self.sleep()
        except Exception as exc:
            logger.warning("Sarasota: form submit failed: %s", repr(exc))

    def _parse_results(self, page) -> list[dict]:
        """
        Parse the ASP.NET GridView results table from the current page.

        Bug 2 fix: replace the non-existent ``table.results-table`` selector
        with a robust search for any GridView table, then fall back to the
        first table on the page.
        """
        html = page.content()
        soup = self.parse_html(html)

        # Try to find a GridView table by its auto-generated id pattern first.
        table = soup.find("table", id=lambda x: x and "Grid" in x)
        if table is None:
            # Fall back to the first <table> that contains <tr> rows with <td>
            for t in soup.find_all("table"):
                if t.find("td"):
                    table = t
                    break

        rows_data: list[dict] = []
        if table is None:
            return rows_data

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            rows_data.append(
                {
                    "instrument_type": self.safe_text(cells[0]),
                    "grantor": self.safe_text(cells[1]),
                    "grantee": self.safe_text(cells[2]),
                    "rec_date": self.safe_text(cells[3]),
                    "book_page": self.safe_text(cells[4]) if len(cells) > 4 else "",
                    "parcel_id": self.safe_text(cells[5]) if len(cells) > 5 else "",
                }
            )
        return rows_data

    # ------------------------------------------------------------------
    # Lead-type specific scrapers
    # ------------------------------------------------------------------

    def _fetch_flippers(self, max_results: int) -> List[PropertyRecord]:
        """
        Identify properties with ≥2 deed transfers within 12 months by
        searching for 'DEED' instrument type over the past 12 months.
        """
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()

            date_to = datetime.now().strftime("%m/%d/%Y")
            date_from = (datetime.now() - timedelta(days=365)).strftime("%m/%d/%Y")

            self._search_official_records(page, "DEED", date_from, date_to)

            rows = self._parse_results(page)

            parcel_transfers: dict[str, list[dict]] = {}
            for row in rows:
                instrument_type = row["instrument_type"]
                if "deed" not in instrument_type.lower():
                    continue
                parcel_id = row["parcel_id"] or row["book_page"] or row["grantor"]
                parcel_transfers.setdefault(parcel_id, []).append(
                    {
                        "date": row["rec_date"],
                        "grantor": row["grantor"],
                        "grantee": row["grantee"],
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
            logger.error("Sarasota flipper scrape failed: %s", repr(exc))

        logger.info("Sarasota flippers found: %d", len(records))
        return records

    def _fetch_high_interest(self, max_results: int) -> List[PropertyRecord]:
        """
        Search for Mortgage Deeds recorded in 2022-2023 (peak rates).
        """
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()

            self._search_official_records(
                page, "MORTGAGE", "01/01/2022", "12/31/2023"
            )

            rows = self._parse_results(page)
            for row in rows:
                if len(records) >= max_results:
                    break
                instrument_type = row["instrument_type"]
                rec_date = row["rec_date"]
                if not self.is_high_equity(rec_date, instrument_type):
                    continue
                rec = PropertyRecord(
                    owner_name=row["grantee"],
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
            logger.error("Sarasota high-interest scrape failed: %s", repr(exc))

        logger.info("Sarasota high-interest found: %d", len(records))
        return records

    def _fetch_past_financing(self, max_results: int) -> List[PropertyRecord]:
        """
        Search for Certificate of Title or Satisfaction of Mortgage instruments.
        """
        records: List[PropertyRecord] = []
        try:
            page = self.new_page()

            for doc_type in ("SATISFACTION OF MORTGAGE", "CERTIFICATE OF TITLE"):
                if len(records) >= max_results:
                    break
                self._search_official_records(
                    page, doc_type, "01/01/2020", "12/31/2024"
                )
                rows = self._parse_results(page)
                for row in rows:
                    if len(records) >= max_results:
                        break
                    instrument_type = row["instrument_type"]
                    if not self.is_past_financing(instrument_type):
                        continue
                    rec_date = row["rec_date"]
                    rec = PropertyRecord(
                        owner_name=row["grantee"],
                        last_sale_date=rec_date,
                        estimated_interest_rate=estimate_interest_rate(rec_date),
                        deed_type=instrument_type,
                        county=self.county_name,
                        lead_type=LeadType.PAST_FINANCING.value,
                    )
                    records.append(rec)

            page.context.close()
        except Exception as exc:
            logger.error("Sarasota past-financing scrape failed: %s", repr(exc))

        logger.info("Sarasota past-financing found: %d", len(records))
        return records
