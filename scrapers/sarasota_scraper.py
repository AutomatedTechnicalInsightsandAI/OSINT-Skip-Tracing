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
import requests

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
    PA_PARCEL_URL = "https://www.sc-pa.com/propertysearch/parcel/details/{parcel_id}"

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

    @staticmethod
    def _clean_currency(value: str) -> str:
        return (value or "").replace("$", "").replace(",", "").strip()

    @staticmethod
    def _safe_join(lines: list[str]) -> str:
        return ", ".join([line.strip(" ,") for line in lines if line.strip(" ,")])

    def _fetch_pa_details(self, parcel_id: str) -> dict:
        """
        Pull supplemental parcel details from the Sarasota Property Appraiser.

        The PA site exposes the last recorded consideration (sale price proxy),
        values, owner/mailing data, situs address, and year built. It does not
        expose a queryable mortgage amount field, so any mortgage value derived
        here is explicitly a proxy.
        """
        normalized_id = self.normalize_parcel_id(parcel_id)
        if not normalized_id:
            return {}

        url = self.PA_PARCEL_URL.format(parcel_id=normalized_id)
        try:
            resp = requests.get(
                url,
                timeout=20,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    )
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Sarasota PA lookup failed for parcel %s: %s",
                normalized_id,
                repr(exc),
            )
            return {}

        soup = self.parse_html(resp.text)
        details: dict[str, str] = {"parcel_id": normalized_id, "pa_detail_url": url}

        left_items = [
            self.safe_text(li) for li in soup.select("ul.resultl.spaced li")
        ]
        owner_lines: list[str] = []
        mailing_lines: list[str] = []
        current_section = None
        for item in left_items:
            lower = item.lower()
            if "ownership:" in lower:
                current_section = "ownership"
                continue
            if "situs address:" in lower:
                current_section = "situs"
                continue
            if "change mailing address" in lower:
                continue
            if current_section == "ownership":
                if item and any(char.isdigit() for char in item):
                    mailing_lines.append(item)
                    current_section = "mailing"
                    continue
                if item:
                    owner_lines.append(item)
                continue
            if current_section == "mailing":
                if item:
                    mailing_lines.append(item)
                continue
            if current_section == "situs":
                details["property_address"] = item
                continue
            if item:
                mailing_lines.append(item)

        if owner_lines:
            details["owner_name"] = " & ".join(owner_lines)
        if mailing_lines:
            details["mailing_address"] = self._safe_join(mailing_lines)

        for li in soup.select("ul.resultr.spaced li"):
            strong = li.find("strong")
            label = self.safe_text(strong).rstrip(":").lower() if strong else ""
            text = self.safe_text(li)
            value = text.replace(self.safe_text(strong), "", 1).strip(" :") if strong else text
            if label == "property use":
                details["property_type"] = value
            elif label == "land area":
                details["land_area"] = value

        for table in soup.find_all("table"):
            headers = [self.safe_text(th) for th in table.find_all("th")]
            if not headers:
                continue

            if headers[:5] == [
                "Year",
                "Land",
                "Building",
                "Extra Feature",
                "Just",
            ]:
                row = table.find("tbody").find("tr") if table.find("tbody") else None
                if row:
                    cells = [self.safe_text(td) for td in row.find_all("td")]
                    if len(cells) >= 8:
                        details["just_value"] = self._clean_currency(cells[4])
                        details["assessed_value"] = self._clean_currency(cells[5])
                        details["taxable_value"] = self._clean_currency(cells[7])

            elif headers[:6] == [
                "Transfer Date",
                "Recorded Consideration",
                "Instrument Number",
                "Qualification Code",
                "Grantor/Seller",
                "Instrument Type",
            ]:
                row = table.find("tbody").find("tr") if table.find("tbody") else None
                if row:
                    cells = [self.safe_text(td) for td in row.find_all("td")]
                    if len(cells) >= 6:
                        details["last_sale_date"] = cells[0]
                        details["sale_price"] = self._clean_currency(cells[1])
                        details["instrument_number"] = cells[2]
                        details["seller_name"] = cells[4]
                        details["sale_instrument_type"] = cells[5]
                        if details["sale_price"]:
                            try:
                                sale_price = float(details["sale_price"])
                                details["mtg_amt_at_purchase"] = str(int(round(sale_price * 0.80)))
                                details["mtg_amt_source"] = (
                                    "Proxy: 80% of Sarasota PA recorded consideration"
                                )
                            except ValueError:
                                pass

            elif headers[:6] == [
                "Situs - click address for building details",
                "Bldg #",
                "Beds",
                "Baths",
                "Half Baths",
                "Year Built",
            ]:
                row = table.find("tbody").find("tr") if table.find("tbody") else None
                if row:
                    cells = [self.safe_text(td) for td in row.find_all("td")]
                    if len(cells) >= 6:
                        details["year_built"] = cells[5]

        mailing = details.get("mailing_address", "")
        situs = details.get("property_address", "")
        if mailing and situs:
            details["absentee_owner"] = str(
                self._normalize_address(mailing) != self._normalize_address(situs)
            )

        return details

    @staticmethod
    def _normalize_address(value: str) -> str:
        return " ".join((value or "").upper().replace(",", " ").split())

    def _enrich_record_from_pa(self, record: PropertyRecord) -> PropertyRecord:
        details = self._fetch_pa_details(record.parcel_id)
        if not details:
            return record

        record.parcel_id = details.get("parcel_id", record.parcel_id)
        record.owner_name = details.get("owner_name", record.owner_name)
        record.property_address = details.get("property_address", record.property_address)
        record.mailing_address = details.get("mailing_address", record.mailing_address)
        record.sale_price = details.get("sale_price", record.sale_price)
        record.just_value = details.get("just_value", record.just_value)
        record.assessed_value = details.get("assessed_value", record.assessed_value)
        record.taxable_value = details.get("taxable_value", record.taxable_value)
        record.mtg_amt_at_purchase = details.get(
            "mtg_amt_at_purchase", record.mtg_amt_at_purchase
        )
        record.mtg_amt_source = details.get("mtg_amt_source", record.mtg_amt_source)
        record.year_built = details.get("year_built", record.year_built)
        record.property_type = details.get("property_type", record.property_type)
        record.absentee_owner = details.get("absentee_owner", record.absentee_owner)

        if not record.last_sale_date:
            record.last_sale_date = details.get("last_sale_date", record.last_sale_date)

        notes = [record.notes] if record.notes else []
        if record.mtg_amt_source:
            notes.append(record.mtg_amt_source)
        record.notes = " | ".join(dict.fromkeys([note for note in notes if note]))
        return record

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
                parcel_id = self.normalize_parcel_id(parcel_id) or parcel_id
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
                    rec = self._enrich_record_from_pa(rec)
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
                    parcel_id=self.normalize_parcel_id(row.get("parcel_id", "")),
                    last_sale_date=rec_date,
                    estimated_interest_rate=estimate_interest_rate(rec_date),
                    deed_type=instrument_type,
                    county=self.county_name,
                    lead_type=LeadType.HIGH_INTEREST.value,
                    notes="Peak-rate mortgage or no mortgage >20 years",
                )
                rec = self._enrich_record_from_pa(rec)
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
                        parcel_id=self.normalize_parcel_id(row.get("parcel_id", "")),
                        last_sale_date=rec_date,
                        estimated_interest_rate=estimate_interest_rate(rec_date),
                        deed_type=instrument_type,
                        county=self.county_name,
                        lead_type=LeadType.PAST_FINANCING.value,
                    )
                    rec = self._enrich_record_from_pa(rec)
                    records.append(rec)

            page.context.close()
        except Exception as exc:
            logger.error("Sarasota past-financing scrape failed: %s", repr(exc))

        logger.info("Sarasota past-financing found: %d", len(records))
        return records
