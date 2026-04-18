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

import csv
import io
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set
from urllib.parse import urljoin, urlparse, parse_qs
import requests

from scrapers.base_scraper import (
    BaseScraper,
    LeadType,
    PropertyRecord,
    estimate_interest_rate,
    parse_record_date,
)
from utils.pdf_reader import extract_mortgage_document_info

logger = logging.getLogger(__name__)


class SarasotaScraper(BaseScraper):
    """Scraper for Sarasota County, FL."""

    # Bug 1 fix: use the correct ASP.NET search portal URL.
    CLERK_URL = "https://secure.sarasotaclerk.com/OfficialRecords.aspx"
    PA_URL = "https://www.sc-pa.com/propertysearch"
    PA_RESULT_URL = "https://www.sc-pa.com/propertysearch/Result"
    PA_EXPORT_URL = "https://www.sc-pa.com/propertysearch/Search/ExportToCsv?qid={qid}"
    PA_PARCEL_URL = "https://www.sc-pa.com/propertysearch/parcel/details/{parcel_id}"
    DOC_TYPE_ALIASES = {
        "CERTIFICATE OF TITLE": "CERT OF TITLE",
    }
    CASHOUT_SALE_FROM = datetime(2023, 7, 1)
    CASHOUT_SALE_TO = datetime(2024, 9, 30)
    CASHOUT_MIN_SALE_PRICE = 250_000
    MORTGAGE_LOOKBACK_DAYS = 7
    MORTGAGE_LOOKAHEAD_DAYS = 21
    CASHOUT_CANDIDATE_MULTIPLIER = 2
    CASHOUT_MIN_CANDIDATES_TO_CHECK = 75
    TARGET_QUALIFICATION_CODES = {"01"}
    NON_PERSON_TOKENS = {"TRUST", "TR", "TTEE", "TRUSTEE", "LLC", "INC", "CORP", "CORPORATION", "LP", "LTD", "LC", "CO"}
    CACHE_PATH = Path(".cache") / "sarasota_mortgage_lookup.json"
    MATURING_SEARCH_YEARS = (2021, 2020, 2019, 2018, 2017, 2016, 2015)
    MATURING_SCAN_LIMIT_MULTIPLIER = 12
    MATURING_SCAN_MINIMUM = 60
    TARGETED_BALLOON_WINDOW_DAYS = 183
    TARGETED_MIN_INTEREST_RATE = 8.0
    COMMERCIAL_ENTITY_TOKENS = {
        "LLC",
        "L.L.C",
        "INC",
        "CORP",
        "CORPORATION",
        "LP",
        "L.P",
        "LLP",
        "LTD",
        "LIMITED",
        "COMPANY",
        "PARTNERSHIP",
        "PARTNERS",
        "HOLDINGS",
        "PROPERTIES",
        "PROPERTY",
        "INVESTMENTS",
        "VENTURES",
        "ENTERPRISES",
        "GROUP",
        "REALTY",
        "DEVELOPMENT",
        "MANAGEMENT",
        "APARTMENTS",
        "OFFICE",
        "INDUSTRIAL",
        "WAREHOUSE",
        "RETAIL",
        "HOTEL",
        "MOTEL",
        "STORAGE",
        "MEDICAL",
    }
    COMMERCIAL_DOC_PHRASES = {
        "COMMERCIAL",
        "BUSINESS PURPOSE",
        "ASSIGNMENT OF LEASES AND RENTS",
        "ASSIGNMENT OF RENTS",
        "SECURITY AGREEMENT",
        "FIXTURE FILING",
        "UCC",
        "LOAN AGREEMENT",
        "ENVIRONMENTAL INDEMNITY",
        "RENTS AND PROFITS",
    }
    CONSUMER_DOC_PHRASES = {
        "HOME EQUITY LINE OF CREDIT",
        "EQUITY LINE OF CREDIT",
        "ONE-TO-FOUR FAMILY",
        "1-4 FAMILY",
        "PLANNED UNIT DEVELOPMENT RIDER",
        "CONDOMINIUM RIDER",
        "SECOND HOME RIDER",
        "FHA",
        "VA GUARANTEED",
    }
    COMMERCIAL_PROPERTY_HINTS = {
        "COMMERCIAL",
        "OFFICE",
        "RETAIL",
        "STORE",
        "WAREHOUSE",
        "INDUSTRIAL",
        "MIXED USE",
        "MIXED-USE",
        "APARTMENT",
        "MULTIFAMILY",
        "MULTI FAMILY",
        "HOTEL",
        "MOTEL",
        "MARINA",
        "MEDICAL",
        "PROFESSIONAL",
        "RESTAURANT",
        "SHOPPING",
        "SELF STORAGE",
        "STORAGE",
        "CHURCH",
        "VACANT COMMERCIAL",
    }
    RESIDENTIAL_PROPERTY_HINTS = {
        "SINGLE FAMILY",
        "CONDOMINIUM",
        "CONDO",
        "TOWNHOUSE",
        "RESIDENTIAL",
        "MOBILE HOME",
        "VACANT RESIDENTIAL",
        "HOMESTEAD",
    }
    OWNER_SEARCH_STOPWORDS = {
        "THE",
        "OF",
        "AND",
        "DATED",
        "ALL",
        "AMENDMENTS",
        "THERETO",
        "THERET",
        "AGREEMENT",
        "TRUSTEE",
        "TRUSTEES",
    }
    INSTITUTIONAL_NAME_TOKENS = {
        "BANK",
        "BANCORP",
        "CREDIT",
        "UNION",
        "MORTGAGE",
        "LOAN",
        "LENDING",
        "SERVICING",
        "CAPITAL",
        "FUND",
        "FUNDS",
        "FINANCE",
        "FINANCIAL",
        "TRUST",
        "TRUSTEE",
        "CORP",
        "CORPORATION",
        "INC",
        "LLC",
        "LP",
        "LTD",
        "COMPANY",
        "CO",
        "HOLDINGS",
        "PROPERTIES",
        "VENTURES",
        "ASSOCIATION",
        "NATIONAL",
        "FEDERAL",
        "NA",
        "N.A",
        "PLC",
        "GROUP",
        "PARTNERS",
        "PARTNERSHIP",
    }
    PERSONAL_NAME_SUFFIXES = {"JR", "SR", "II", "III", "IV", "V"}
    PERSONAL_NAME_STOPWORDS = {
        "AND",
        "HUSBAND",
        "WIFE",
        "MARRIED",
        "SINGLE",
        "MAN",
        "WOMAN",
        "JOINT",
        "TENANTS",
        "BY",
        "ENTIRETIES",
        "AS",
    }
    BALLOON_SIGNAL_PHRASES = {
        "BALLOON",
        "BALLOON PAYMENT",
        "ENTIRE ACCOUNT BALANCE",
        "ENTIRE UNPAID PRINCIPAL BALANCE",
        "ENTIRE PRINCIPAL BALANCE",
        "ALL SUMS SECURED BY THIS SECURITY INSTRUMENT",
        "FINAL PAYMENT",
    }

    def __init__(self, headless: bool = False, timeout_ms: int = 30_000):
        super().__init__(headless=headless, timeout_ms=timeout_ms)
        self._mortgage_lookup_cache = self._load_mortgage_cache()
        self._owner_search_cache: dict[str, list[dict[str, str]]] = {}
        self._pa_details_cache: dict[str, dict[str, str]] = {}

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

        # ⚠️ DO NOT CHANGE
        if lead_type == LeadType.CASHOUT_REFI:
            return self._fetch_cashout_refi(max_results)
        if lead_type == LeadType.BALLOON_PROSPECTS:
            return self._fetch_balloon_prospects(max_results)
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
        party_last: str = "",
        party_first: str = "",
    ) -> None:
        """
        Navigate to the Sarasota ASP.NET Official Records portal and submit a
        search for *doc_type* within the given date range.

        Bug 3 fix: actually fill in and submit the search form instead of just
        reading the landing page HTML.
        """
        page.goto(self.CLERK_URL, wait_until="domcontentloaded", timeout=30_000)
        self.sleep()
        self.random_scroll(page)

        self._select_doc_type(page, doc_type)
        self._fill_party_name(page, party_last, party_first)

        try:
            page.fill("#ctl00_cphBody_rdAppFrom_dateInput", date_from)
        except Exception as exc:
            logger.warning("Sarasota: could not fill DateFrom: %s", repr(exc))

        try:
            page.fill("#ctl00_cphBody_rdAppTo_dateInput", date_to)
        except Exception as exc:
            logger.warning("Sarasota: could not fill DateTo: %s", repr(exc))

        try:
            page.click("#ctl00_cphBody_bSearch_input")
            try:
                page.wait_for_load_state("load", timeout=15_000)
            except Exception:
                pass
            try:
                page.wait_for_selector(
                    "#ctl00_cphBody_rgCaseList table, table",
                    timeout=10_000,
                    state="visible",
                )
            except Exception:
                pass
            self.sleep()
        except Exception as exc:
            logger.warning("Sarasota: form submit failed: %s", repr(exc))

    def _load_mortgage_cache(self) -> dict[str, bool]:
        """Load persisted Sarasota mortgage lookup decisions from disk."""
        try:
            if not self.CACHE_PATH.exists():
                return {}
            with self.CACHE_PATH.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                return {str(key): bool(value) for key, value in payload.items()}
        except Exception as exc:
            logger.warning("Sarasota: could not load mortgage cache: %s", repr(exc))
        return {}

    def _save_mortgage_cache(self) -> None:
        """Persist mortgage lookup cache so reruns can reuse prior checks."""
        try:
            self.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.CACHE_PATH.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(self._mortgage_lookup_cache, handle, indent=2, sort_keys=True)
            temp_path.replace(self.CACHE_PATH)
        except Exception as exc:
            logger.warning("Sarasota: could not save mortgage cache: %s", repr(exc))

    @staticmethod
    def _mortgage_cache_key(
        search_name: str,
        party_last: str,
        party_first: str,
        date_from: str,
        date_to: str,
    ) -> str:
        return "|".join(
            [
                "MORTGAGE",
                search_name.upper(),
                party_last.upper(),
                party_first.upper(),
                date_from,
                date_to,
            ]
        )

    def _fill_party_name(self, page, party_last: str, party_first: str) -> None:
        """Fill Sarasota's Party/Company search inputs when provided."""
        if not party_last and not party_first:
            return

        try:
            page.fill("#ctl00_cphBody_tbParty", party_last or "")
        except Exception as exc:
            logger.warning("Sarasota: could not fill party/company field: %s", repr(exc))

        try:
            page.fill("#ctl00_cphBody_tbPartyFirst", party_first or "")
        except Exception as exc:
            logger.warning("Sarasota: could not fill party first-name field: %s", repr(exc))

    def _select_doc_type(self, page, doc_type: str) -> None:
        """
        Sarasota exposes document types as checkbox labels, not a <select>.
        """
        target = self.DOC_TYPE_ALIASES.get(doc_type, doc_type)
        labels = page.locator("label[for]")

        try:
            label_count = labels.count()
            for idx in range(label_count):
                label = labels.nth(idx)
                label_text = " ".join((label.inner_text() or "").split()).upper()
                if label_text != target.upper():
                    continue
                checkbox_id = label.get_attribute("for")
                if checkbox_id:
                    page.locator(f"#{checkbox_id}").scroll_into_view_if_needed()
                    page.check(f"#{checkbox_id}")
                    logger.info("Sarasota: selected document type '%s'", target)
                    return
        except Exception:
            pass

        try:
            matching = page.locator("label").filter(has_text=target).first
            checkbox_id = matching.get_attribute("for")
            if checkbox_id:
                page.check(f"#{checkbox_id}")
                logger.info(
                    "Sarasota: used partial document type match '%s' for '%s'",
                    target,
                    doc_type,
                )
                return
        except Exception:
            pass

        logger.warning("Sarasota: could not select doc type checkbox '%s'", doc_type)

    def _parse_results(self, page) -> list[dict]:
        """
        Parse the ASP.NET GridView results table from the current page.

        Bug 2 fix: replace the non-existent ``table.results-table`` selector
        with a robust search for any GridView table, then fall back to the
        first table on the page.
        """
        html = page.content()
        soup = self.parse_html(html)

        table = soup.select_one("#ctl00_cphBody_rgCaseList table")
        if table is None:
            for candidate in soup.find_all("table"):
                headers = [self.safe_text(th).lower() for th in candidate.find_all("th")]
                if {"date recorded", "document type", "name"}.issubset(headers):
                    table = candidate
                    break

        rows_data: list[dict] = []
        if table is None:
            return rows_data

        header_row = None
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
        headers = (
            [self.safe_text(th).lower() for th in header_row.find_all("th", recursive=False)]
            if header_row
            else []
        )
        header_index = {header: idx for idx, header in enumerate(headers)}

        if "document type" in header_index and "date recorded" in header_index:
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 7:
                    continue
                first_cell_text = self.safe_text(cells[0]).lower()
                if "view image" not in first_cell_text:
                    continue
                image_link = ""
                if cells:
                    first_anchor = cells[0].find("a")
                    if first_anchor and first_anchor.get("href"):
                        image_link = urljoin(self.CLERK_URL, first_anchor.get("href"))
                rows_data.append(
                    {
                        "image_url": image_link,
                        "instrument_number": self.safe_text(
                            cells[header_index.get("instrument number", 1)]
                        ),
                        "instrument_type": self.safe_text(
                            cells[header_index["document type"]]
                        ),
                        "grantor": "",
                        "grantee": self.safe_text(cells[header_index.get("name", 0)]),
                        "rec_date": self.safe_text(
                            cells[header_index["date recorded"]]
                        ),
                        "book_page": self.safe_text(cells[header_index.get("book-page", 0)]),
                        "parcel_id": "",
                        "legal_description": self.safe_text(
                            cells[header_index.get("legal description", 0)]
                        ),
                    }
                )
            return rows_data

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
        if normalized_id in self._pa_details_cache:
            return dict(self._pa_details_cache[normalized_id])

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
                        details["current_exemptions"] = self._clean_currency(cells[6])
                        details["taxable_value"] = self._clean_currency(cells[7])
                        if len(cells) >= 9:
                            details["cap_value"] = self._clean_currency(cells[8])
                        try:
                            exemptions_amount = float(details.get("current_exemptions", "0") or 0)
                        except ValueError:
                            exemptions_amount = 0.0
                        try:
                            cap_amount = float(details.get("cap_value", "0") or 0)
                        except ValueError:
                            cap_amount = 0.0
                        details["has_current_exemption"] = str(
                            exemptions_amount > 0 or cap_amount > 0
                        )

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

        self._pa_details_cache[normalized_id] = dict(details)
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
        record.current_exemptions = details.get("current_exemptions", record.current_exemptions)
        record.absentee_owner = details.get("absentee_owner", record.absentee_owner)

        if not record.last_sale_date:
            record.last_sale_date = details.get("last_sale_date", record.last_sale_date)

        notes = [record.notes] if record.notes else []
        if record.mtg_amt_source:
            notes.append(record.mtg_amt_source)
        record.notes = " | ".join(dict.fromkeys([note for note in notes if note]))
        return record

    def _extract_mortgage_pdf_terms(self, pdf_source: bytes | str | Path) -> dict[str, str]:
        """
        Parse a Sarasota mortgage PDF into lead-friendly fields.

        This is the OCR-backed path for image-only clerk PDFs. The live scraper
        can call it once we have the document download wired to a search result.
        """
        info = extract_mortgage_document_info(pdf_source)
        return {
            "instrument_number": info.instrument_number,
            "borrower_name": info.borrower_name,
            "lender_name": info.lender_name,
            "credit_limit": info.credit_limit,
            "interest_rate": info.interest_rate,
            "maturity_date": info.maturity_date,
            "doc_stamp_mortgage": info.doc_stamp_mortgage,
            "intangible_tax": info.intangible_tax,
            "extraction_method": info.extraction_method,
            "pdf_text": info.extracted_text,
        }

    def _download_clerk_pdf(
        self,
        *,
        image_url: str = "",
        instrument_number: str = "",
    ) -> bytes:
        """Download a Sarasota clerk PDF for a result row."""
        url = image_url.strip()
        if not url and instrument_number.strip():
            url = urljoin(
                self.CLERK_URL,
                f"/viewTiff.aspx?intrnum={instrument_number.strip()}",
            )
        if not url:
            return b""

        try:
            response = requests.get(
                url,
                timeout=60,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    )
                },
            )
            response.raise_for_status()
            return response.content
        except Exception as exc:
            logger.warning("Sarasota clerk PDF download failed for %s: %s", url, repr(exc))
            return b""

    def _apply_clerk_pdf_terms(
        self,
        record: PropertyRecord,
        row: dict,
        terms: dict[str, str],
    ) -> PropertyRecord:
        """Apply already-extracted Sarasota clerk PDF terms to a record."""
        image_url = row.get("image_url", "")
        instrument_number = row.get("instrument_number", "")
        record.instrument_number = terms.get("instrument_number", "") or instrument_number
        record.view_image_url = image_url
        record.owner_name = terms.get("borrower_name", "") or record.owner_name
        record.lender_name = terms.get("lender_name", "")
        record.maturity_date = terms.get("maturity_date", "")
        record.pdf_extraction_method = terms.get("extraction_method", "")

        credit_limit = terms.get("credit_limit", "")
        if credit_limit:
            record.mtg_amt_at_purchase = credit_limit
            record.mtg_amt_source = "Sarasota Clerk OCR: Credit Limit from recorded mortgage PDF"
        if terms.get("interest_rate"):
            record.estimated_interest_rate = terms["interest_rate"]

        extra_notes: list[str] = []
        if record.lender_name:
            extra_notes.append(f"Lender: {record.lender_name}")
        if terms.get("interest_rate"):
            extra_notes.append(f"Interest Rate: {terms['interest_rate']}")
        if record.maturity_date:
            extra_notes.append(f"Maturity Date: {record.maturity_date}")
        if terms.get("doc_stamp_mortgage"):
            extra_notes.append(f"Doc Stamp: ${terms['doc_stamp_mortgage']}")
        if terms.get("intangible_tax"):
            extra_notes.append(f"Intangible Tax: ${terms['intangible_tax']}")
        if extra_notes:
            joined = " | ".join(extra_notes)
            record.notes = " | ".join([part for part in [record.notes, joined] if part])

        if record.lead_source:
            if "OCR" not in record.lead_source:
                record.lead_source = f"{record.lead_source} + OCR"
        else:
            record.lead_source = "Sarasota Official Records + OCR"

        return record

    def _enrich_record_from_clerk_pdf(self, record: PropertyRecord, row: dict) -> PropertyRecord:
        """
        Attach OCR-derived mortgage terms from a Sarasota clerk PDF to a record.
        """
        image_url = row.get("image_url", "")
        instrument_number = row.get("instrument_number", "")
        if not image_url and not instrument_number:
            return record

        pdf_bytes = self._download_clerk_pdf(
            image_url=image_url,
            instrument_number=instrument_number,
        )
        if not pdf_bytes:
            return record

        terms = self._extract_mortgage_pdf_terms(pdf_bytes)
        return self._apply_clerk_pdf_terms(record, row, terms)

    @staticmethod
    def _normalize_owner_match_text(value: str) -> str:
        cleaned = " ".join((value or "").upper().replace(",", " ").split())
        return "".join(char if char.isalnum() or char == " " else " " for char in cleaned).strip()

    def _build_owner_search_query(self, owner_name: str) -> str:
        cleaned = self._clean_owner_name(owner_name)
        tokens = [
            token
            for token in cleaned.split()
            if token not in self.OWNER_SEARCH_STOPWORDS
        ]
        return " ".join(tokens[:6]).strip()

    def _fetch_pa_owner_rows(self, owner_name: str) -> list[dict[str, str]]:
        """Search Sarasota PA by owner keywords and return CSV rows."""
        query = self._build_owner_search_query(owner_name)
        if not query:
            return []
        cache_key = self._normalize_owner_match_text(query)
        if cache_key in self._owner_search_cache:
            return self._owner_search_cache[cache_key]

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
        try:
            response = requests.post(
                self.PA_RESULT_URL,
                data={"OwnerKeywords": query},
                timeout=30,
                headers=headers,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Sarasota PA owner search failed for %s: %s", query, repr(exc))
            self._owner_search_cache[cache_key] = []
            return []

        qid = parse_qs(urlparse(response.url).query).get("qid", [""])[0]
        if not qid:
            self._owner_search_cache[cache_key] = []
            return []

        try:
            export_response = requests.get(
                self.PA_EXPORT_URL.format(qid=qid),
                timeout=60,
                headers=headers,
            )
            export_response.raise_for_status()
        except Exception as exc:
            logger.warning("Sarasota PA owner CSV export failed for %s: %s", query, repr(exc))
            self._owner_search_cache[cache_key] = []
            return []

        csv_text = export_response.text.lstrip("\ufeff")
        csv_lines = csv_text.splitlines()
        if csv_lines and csv_lines[0].startswith("NOTE:"):
            csv_text = "\n".join(csv_lines[1:])

        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self._owner_search_cache[cache_key] = rows
        return rows

    @classmethod
    def _looks_commercial_property_type(cls, value: str) -> bool:
        upper_value = " ".join((value or "").upper().split())
        return any(hint in upper_value for hint in cls.COMMERCIAL_PROPERTY_HINTS)

    @classmethod
    def _looks_residential_property_type(cls, value: str) -> bool:
        upper_value = " ".join((value or "").upper().split())
        return any(hint in upper_value for hint in cls.RESIDENTIAL_PROPERTY_HINTS)

    @classmethod
    def _has_commercial_entity_token(cls, owner_name: str) -> bool:
        tokens = {
            token.strip(".,")
            for token in " ".join((owner_name or "").upper().split()).split()
        }
        return any(token in cls.COMMERCIAL_ENTITY_TOKENS for token in tokens)

    def _enrich_record_from_pa_owner_search(self, record: PropertyRecord, owner_name: str) -> PropertyRecord:
        """Use Sarasota PA owner search when we can safely identify a parcel."""
        rows = self._fetch_pa_owner_rows(owner_name)
        if not rows:
            return record

        target_norm = self._normalize_owner_match_text(owner_name)
        query_norm = self._normalize_owner_match_text(self._build_owner_search_query(owner_name))
        matched_rows: list[dict[str, str]] = []

        for row in rows:
            owner_text = " ".join(
                [
                    row.get("Owner 1", "") or "",
                    row.get("Owner 2", "") or "",
                    row.get("Owner 3", "") or "",
                ]
            )
            owner_norm = self._normalize_owner_match_text(owner_text)
            if not owner_norm:
                continue
            if target_norm and (target_norm in owner_norm or owner_norm in target_norm):
                matched_rows.append(row)
                continue
            if query_norm and query_norm in owner_norm:
                matched_rows.append(row)

        if not matched_rows:
            return record

        commercial_rows = [
            row
            for row in matched_rows
            if self._looks_commercial_property_type(
                f"{row.get('Description', '')} {row.get('Property Use Code', '')}"
            )
        ]

        selected_row: dict[str, str] | None = None
        if len(commercial_rows) == 1:
            selected_row = commercial_rows[0]
        elif len(matched_rows) == 1:
            selected_row = matched_rows[0]

        if not selected_row:
            return record

        parcel_id = self.normalize_parcel_id(selected_row.get("Account #", ""))
        if parcel_id:
            record.parcel_id = parcel_id
        if not record.property_address:
            record.property_address = (selected_row.get("Situs Address", "") or "").strip()
        if not record.mailing_address:
            record.mailing_address = (selected_row.get("Mailing Address", "") or "").strip()
        if not record.property_type:
            record.property_type = (selected_row.get("Description", "") or "").strip()

        if parcel_id:
            record = self._enrich_record_from_pa(record)
        return record

    def _is_likely_commercial_mortgage(
        self,
        borrower_name: str,
        pdf_text: str,
        property_type: str = "",
    ) -> tuple[bool, str]:
        """Return whether a Sarasota mortgage looks commercial enough for this lead path."""
        upper_text = " ".join((pdf_text or "").upper().split())
        upper_property_type = " ".join((property_type or "").upper().split())

        if any(phrase in upper_text for phrase in self.CONSUMER_DOC_PHRASES):
            return False, "consumer-doc-phrase"
        if upper_property_type and self._looks_residential_property_type(upper_property_type):
            return False, "residential-property-type"
        if any(phrase in upper_text for phrase in self.COMMERCIAL_DOC_PHRASES):
            return True, "commercial-doc-phrase"
        if upper_property_type and self._looks_commercial_property_type(upper_property_type):
            return True, "commercial-property-type"
        if self._has_commercial_entity_token(borrower_name):
            return True, "entity-borrower"
        return False, "no-commercial-signal"

    @classmethod
    def _parse_percent(cls, value: str) -> float:
        cleaned = " ".join((value or "").split())
        if not cleaned:
            return 0.0
        match = re.search(r"([0-9]{1,2}(?:\.[0-9]+)?)\s*%", cleaned)
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0

    @classmethod
    def _is_non_homestead_candidate(cls, details: dict[str, str]) -> bool:
        if not details:
            return False
        return str(details.get("has_current_exemption", "")).strip().lower() not in {
            "true",
            "1",
            "yes",
        }

    @classmethod
    def _is_likely_personal_name(cls, value: str) -> bool:
        normalized = " ".join((value or "").upper().replace(",", " ").split())
        if not normalized:
            return False
        cleaned_tokens = []
        for raw_token in normalized.replace("&", " ").replace("/", " ").split():
            token = raw_token.strip("().")
            if not token:
                continue
            if token in cls.PERSONAL_NAME_SUFFIXES:
                continue
            if token in cls.PERSONAL_NAME_STOPWORDS:
                continue
            if token in {"ET", "AL", "AKA"}:
                continue
            if token in cls.INSTITUTIONAL_NAME_TOKENS:
                return False
            alpha = "".join(ch for ch in token if ch.isalpha() or ch == "-")
            if not alpha:
                continue
            cleaned_tokens.append(alpha)

        if len(cleaned_tokens) < 2 or len(cleaned_tokens) > 8:
            return False
        return any(len(token.replace("-", "")) > 1 for token in cleaned_tokens)

    @classmethod
    def _has_balloon_signal(cls, pdf_text: str) -> tuple[bool, str]:
        upper_text = " ".join((pdf_text or "").upper().split())
        for phrase in cls.BALLOON_SIGNAL_PHRASES:
            if phrase in upper_text:
                return True, phrase.lower().replace(" ", "-")
        return False, "no-balloon-signal"

    def _fetch_cashout_refi(self, max_results: int) -> List[PropertyRecord]:
        """
        Find Sarasota purchases from the peak-rate window over $250k with no
        matching mortgage recorded at purchase.
        """
        records: List[PropertyRecord] = []
        try:
            sales = self._fetch_recent_sales_from_pa()
            if not sales:
                logger.info("Sarasota cash-out refi: no PA sales returned")
                return records

            candidate_limit = min(
                len(sales),
                max(
                    max_results * self.CASHOUT_CANDIDATE_MULTIPLIER,
                    self.CASHOUT_MIN_CANDIDATES_TO_CHECK,
                ),
            )
            sales = sales[:candidate_limit]
            logger.info(
                "Sarasota cash-out refi: checking %d candidate sales for no-purchase-mortgage",
                len(sales),
            )

            page = self.new_page()
            checked = 0
            for sale in sales:
                if len(records) >= max_results:
                    break

                owner_name = sale.get("owner_name", "")
                sale_date = sale.get("last_sale_date", "")
                search_names = sale.get("search_names", [])
                if not owner_name or not sale_date:
                    continue

                checked += 1
                if checked == 1 or checked % 10 == 0:
                    logger.info(
                        "Sarasota cash-out refi: mortgage-check progress %d/%d, leads found %d",
                        checked,
                        len(sales),
                        len(records),
                    )

                try:
                    has_mortgage = self._has_purchase_mortgage(
                        page,
                        owner_name,
                        sale_date,
                        search_names=search_names,
                    )
                except Exception as exc:
                    if self._is_target_closed_error(exc):
                        logger.warning(
                            "Sarasota cash-out refi interrupted after %d checks; returning %d partial leads",
                            checked - 1,
                            len(records),
                        )
                        break
                    raise

                if has_mortgage:
                    continue

                records.append(
                    PropertyRecord(
                        owner_name=owner_name,
                        property_address=sale.get("property_address", ""),
                        mailing_address=sale.get("mailing_address", ""),
                        last_sale_date=sale_date,
                        estimated_interest_rate="0% (no mortgage at purchase)",
                        county=self.county_name,
                        lead_type=LeadType.CASHOUT_REFI.value,
                        parcel_id=sale.get("parcel_id", ""),
                        deed_type=sale.get("deed_type", ""),
                        sale_price=sale.get("sale_price", ""),
                        just_value=sale.get("just_value", ""),
                        assessed_value=sale.get("assessed_value", ""),
                        taxable_value=sale.get("taxable_value", ""),
                        mtg_amt_at_purchase="0",
                        mtg_amt_source=(
                            f"No Sarasota mortgage record found within +/- "
                            f"{self.MORTGAGE_LOOKBACK_DAYS}/{self.MORTGAGE_LOOKAHEAD_DAYS} "
                            f"days of sale date"
                        ),
                        year_built=sale.get("year_built", ""),
                        property_type=sale.get("property_type", ""),
                        lead_source="Sarasota PA + Official Records",
                        notes=(
                            "Recent purchase over $250k with no mortgage record "
                            "found at purchase"
                        ),
                    )
                )

            page.context.close()
            logger.info(
                "Sarasota cash-out refi: checked %d candidates, returning %d leads",
                checked,
                len(records),
            )
        except Exception as exc:
            logger.error("Sarasota cash-out refi scrape failed: %s", repr(exc))

        return records

    def _fetch_recent_sales_from_pa(self) -> list[dict]:
        """Use Sarasota PA advanced search/export for target-window sales over the price floor."""
        sale_from = self.CASHOUT_SALE_FROM
        sale_to = self.CASHOUT_SALE_TO
        payload = {
            "SalesFrom": sale_from.strftime("%m/%d/%Y"),
            "SalesTo": sale_to.strftime("%m/%d/%Y"),
            "SaleAmountFrom": str(self.CASHOUT_MIN_SALE_PRICE),
            "PageSize": "1000",
        }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }

        try:
            response = requests.post(
                self.PA_RESULT_URL,
                data=payload,
                timeout=30,
                headers=headers,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Sarasota PA sales search failed: %s", repr(exc))
            return []

        qid = parse_qs(urlparse(response.url).query).get("qid", [""])[0]
        if not qid:
            logger.warning("Sarasota PA sales search returned no qid")
            return []

        try:
            export_response = requests.get(
                self.PA_EXPORT_URL.format(qid=qid),
                timeout=60,
                headers=headers,
            )
            export_response.raise_for_status()
        except Exception as exc:
            logger.warning("Sarasota PA CSV export failed: %s", repr(exc))
            return []

        csv_text = export_response.text.lstrip("\ufeff")
        csv_lines = csv_text.splitlines()
        if csv_lines and csv_lines[0].startswith("NOTE:"):
            csv_text = "\n".join(csv_lines[1:])

        reader = csv.DictReader(io.StringIO(csv_text))
        sales: list[dict] = []
        seen_parcels: set[str] = set()
        for row in reader:
            parcel_id = self.normalize_parcel_id(row.get("Account #", ""))
            if not parcel_id or parcel_id in seen_parcels:
                continue

            sale_date = parse_record_date(row.get("Last Sale Date", ""))
            sale_price = self._to_float(row.get("Last Sale Amount", ""))
            if not sale_date or sale_price < self.CASHOUT_MIN_SALE_PRICE:
                continue
            if sale_date < sale_from or sale_date > sale_to:
                continue

            qual_code = (row.get("Last Qualification Code", "") or "").strip()
            if self.TARGET_QUALIFICATION_CODES and qual_code not in self.TARGET_QUALIFICATION_CODES:
                continue

            deed_type = (row.get("Last Transaction Code", "") or "").strip()
            if not deed_type:
                continue

            seen_parcels.add(parcel_id)
            owners = [
                (row.get("Owner 1", "") or "").strip(),
                (row.get("Owner 2", "") or "").strip(),
                (row.get("Owner 3", "") or "").strip(),
            ]
            owner_name = " & ".join([owner for owner in owners if owner])

            sales.append(
                {
                    "parcel_id": parcel_id,
                    "owner_name": owner_name,
                    "property_address": (row.get("Situs Address", "") or "").strip(),
                    "mailing_address": (row.get("Mailing Address", "") or "").strip(),
                    "sale_price": str(int(round(sale_price))),
                    "last_sale_date": sale_date.strftime("%m/%d/%Y"),
                    "deed_type": deed_type,
                    "just_value": self._clean_currency(row.get("Just Value", "")),
                    "assessed_value": self._clean_currency(row.get("Assessed Value", "")),
                    "taxable_value": self._clean_currency(row.get("Taxable Value", "")),
                    "year_built": (row.get("Year Built", "") or "").strip(),
                    "property_type": (row.get("Description", "") or "").strip(),
                    "search_names": self._build_search_names(owners),
                }
            )

        sales.sort(
            key=lambda row: parse_record_date(row.get("last_sale_date", "")) or datetime.min,
            reverse=True,
        )
        logger.info(
            "Sarasota PA export returned %d peak-window high-price sales",
            len(sales),
        )
        return sales

    def _has_purchase_mortgage(
        self,
        page,
        owner_name: str,
        sale_date: str,
        search_names: list[str] | None = None,
    ) -> bool:
        """Return True when Sarasota Official Records shows a mortgage near closing."""
        sale_dt = parse_record_date(sale_date)
        if not sale_dt:
            return False

        search_names = search_names or self._build_search_names([owner_name])
        if not search_names:
            return False

        date_from = (sale_dt - timedelta(days=self.MORTGAGE_LOOKBACK_DAYS)).strftime("%m/%d/%Y")
        date_to = (sale_dt + timedelta(days=self.MORTGAGE_LOOKAHEAD_DAYS)).strftime("%m/%d/%Y")

        for search_name in search_names:
            party_last, party_first = self._split_owner_search_name(search_name)
            if not party_last:
                continue
            cache_key = self._mortgage_cache_key(
                search_name=search_name,
                party_last=party_last,
                party_first=party_first,
                date_from=date_from,
                date_to=date_to,
            )
            if cache_key in self._mortgage_lookup_cache:
                return self._mortgage_lookup_cache[cache_key]

            logger.info(
                "Sarasota cash-out refi: mortgage search for '%s' using last/business='%s' first='%s' dates %s..%s",
                search_name,
                party_last,
                party_first,
                date_from,
                date_to,
            )

            self._search_official_records(
                page,
                "MORTGAGE",
                date_from,
                date_to,
                party_last=party_last,
                party_first=party_first,
            )

            rows = self._parse_results(page)
            if not rows:
                self._mortgage_lookup_cache[cache_key] = False
                self._save_mortgage_cache()
                continue

            normalized_target = self._normalize_name(search_name)
            for row in rows:
                row_name = self._normalize_name(row.get("grantee", ""))
                if normalized_target and normalized_target == row_name:
                    self._mortgage_lookup_cache[cache_key] = True
                    self._save_mortgage_cache()
                    return True
                if normalized_target and normalized_target in row_name:
                    self._mortgage_lookup_cache[cache_key] = True
                    self._save_mortgage_cache()
                    return True
                if row_name and party_last.upper() in row_name:
                    self._mortgage_lookup_cache[cache_key] = True
                    self._save_mortgage_cache()
                    return True
            self._mortgage_lookup_cache[cache_key] = False
            self._save_mortgage_cache()
        return False

    def _split_owner_search_name(self, owner_name: str) -> tuple[str, str]:
        """Split a single cleaned owner name into Sarasota clerk search fields."""
        clean = self._clean_owner_name(owner_name)
        if not clean:
            return "", ""

        parts = clean.split()
        if len(parts) == 1 or any(token.upper().strip(".,") in self.NON_PERSON_TOKENS for token in parts):
            return clean, ""
        return parts[0], parts[1]

    @staticmethod
    def _normalize_name(value: str) -> str:
        return " ".join((value or "").upper().replace(",", " ").split())

    @staticmethod
    def _to_float(value: str) -> float:
        cleaned = (value or "").replace("$", "").replace(",", "").strip()
        if not cleaned:
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _build_search_names(self, owners: list[str]) -> list[str]:
        """Build ordered mortgage-search names from PA owner fields."""
        search_names: list[str] = []
        for owner in owners:
            cleaned = self._clean_owner_name(owner)
            if not cleaned:
                continue
            if cleaned not in search_names:
                search_names.append(cleaned)

        person_names = [
            name
            for name in search_names
            if not any(token in self.NON_PERSON_TOKENS for token in name.upper().split())
        ]
        if person_names:
            return person_names[:2]
        return search_names[:1]

    @staticmethod
    def _clean_owner_name(owner_name: str) -> str:
        """Normalize PA owner text into a clerk-search-friendly name."""
        clean = (owner_name or "").upper()
        clean = clean.replace("&", " ")
        clean = clean.replace("/", " ")
        clean = clean.replace(",", " ")
        clean = clean.replace("(", " ").replace(")", " ")
        clean = " ".join(clean.split())

        filtered_tokens: list[str] = []
        for token in clean.split():
            stripped = token.strip(".,")
            normalized = stripped.replace("-", "")
            if not stripped:
                continue
            if stripped.isdigit():
                continue
            if stripped in {"1", "2", "3", "1/2", "1/3", "2/3"}:
                continue
            if len(stripped) == 1 and stripped.isdigit():
                continue
            if normalized in {"COTTEE", "TTEE", "TRUSTEE", "COEXECUTOR", "EXECUTOR"}:
                continue
            filtered_tokens.append(stripped)

        return " ".join(filtered_tokens).strip()

    @staticmethod
    def _is_target_closed_error(exc: Exception) -> bool:
        text = repr(exc)
        return "TargetClosedError" in text or "Target page, context or browser has been closed" in text

    def _get_fresh_page(self, stale_page=None):
        """Open a new page context, closing any stale one first."""
        if stale_page is not None:
            try:
                stale_page.context.close()
            except Exception:
                pass
        try:
            return self.new_page()
        except Exception:
            self.start_browser()
            return self.new_page()

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
                parcel_id = (
                    row["parcel_id"]
                    or row.get("legal_description", "")
                    or row["book_page"]
                    or row["grantor"]
                    or row["grantee"]
                )
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
                        lead_type=LeadType.BALLOON_PROSPECTS.value,
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
                    lead_type=LeadType.BALLOON_PROSPECTS.value,
                    instrument_number=row.get("instrument_number", ""),
                    view_image_url=row.get("image_url", ""),
                    notes="Peak-rate mortgage or no mortgage >20 years",
                )
                rec = self._enrich_record_from_pa(rec)
                if "mortgage" in instrument_type.lower():
                    rec = self._enrich_record_from_clerk_pdf(rec, row)
                records.append(rec)

            page.context.close()
        except Exception as exc:
            logger.error("Sarasota high-interest scrape failed: %s", repr(exc))

        logger.info("Sarasota high-interest found: %d", len(records))
        return records

    def _fetch_maturing_commercial_debt(self, max_results: int) -> List[PropertyRecord]:
        """
        Search Sarasota mortgages for OCR-confirmed near-term maturities that
        also show commercial debt signals.
        """
        records: List[PropertyRecord] = []
        seen_instruments: set[str] = set()
        scan_limit = max(
            max_results * self.MATURING_SCAN_LIMIT_MULTIPLIER,
            self.MATURING_SCAN_MINIMUM,
        )
        scanned = 0
        today = datetime.now().date()
        maturity_cutoff = today + timedelta(days=365)

        try:
            page = self.new_page()

            for year in self.MATURING_SEARCH_YEARS:
                if len(records) >= max_results or scanned >= scan_limit:
                    break

                try:
                    self._search_official_records(
                        page,
                        "MORTGAGE",
                        f"01/01/{year}",
                        f"12/31/{year}",
                    )
                    rows = self._parse_results(page)
                except Exception as exc:
                    if self._is_target_closed_error(exc):
                        logger.warning(
                            "Sarasota balloon: page closed mid-search for year %d, reopening",
                            year,
                        )
                        page = self._get_fresh_page(page)
                        try:
                            self._search_official_records(
                                page,
                                "MORTGAGE",
                                f"01/01/{year}",
                                f"12/31/{year}",
                            )
                            rows = self._parse_results(page)
                        except Exception as retry_exc:
                            logger.warning(
                                "Sarasota balloon: retry failed for year %d: %s",
                                year,
                                repr(retry_exc),
                            )
                            continue
                    else:
                        raise

                for row in rows:
                    if len(records) >= max_results or scanned >= scan_limit:
                        break

                    instrument_number = row.get("instrument_number", "").strip()
                    if not instrument_number or instrument_number in seen_instruments:
                        continue
                    seen_instruments.add(instrument_number)

                    pdf_bytes = self._download_clerk_pdf(
                        image_url=row.get("image_url", ""),
                        instrument_number=instrument_number,
                    )
                    if not pdf_bytes:
                        continue

                    scanned += 1
                    terms = self._extract_mortgage_pdf_terms(pdf_bytes)
                    maturity_dt = parse_record_date(terms.get("maturity_date", ""))
                    if not maturity_dt:
                        continue
                    maturity_date = maturity_dt.date()
                    if maturity_date < today or maturity_date > maturity_cutoff:
                        continue

                    borrower_name = terms.get("borrower_name", "").strip() or row.get("grantee", "")
                    if not borrower_name:
                        continue

                    record = PropertyRecord(
                        owner_name=borrower_name,
                        last_sale_date=row.get("rec_date", ""),
                        estimated_interest_rate=estimate_interest_rate(row.get("rec_date", "")),
                        county=self.county_name,
                        deed_type=row.get("instrument_type", ""),
                        lead_type=LeadType.BALLOON_PROSPECTS.value,
                        instrument_number=instrument_number,
                        lead_source="Sarasota Official Records + OCR",
                        notes="OCR-confirmed near-term maturity from Sarasota recorded mortgage",
                    )
                    record = self._apply_clerk_pdf_terms(record, row, terms)
                    record = self._enrich_record_from_pa_owner_search(record, borrower_name)

                    is_commercial, commercial_reason = self._is_likely_commercial_mortgage(
                        borrower_name=record.owner_name,
                        pdf_text=terms.get("pdf_text", ""),
                        property_type=record.property_type,
                    )
                    if not is_commercial:
                        continue

                    note_bits = [record.notes] if record.notes else []
                    note_bits.append(f"Commercial signal: {commercial_reason}")
                    if record.property_type:
                        note_bits.append(f"Property Type: {record.property_type}")
                    record.notes = " | ".join(dict.fromkeys([bit for bit in note_bits if bit]))
                    records.append(record)

            page.context.close()
        except Exception as exc:
            logger.error("Sarasota maturing commercial debt scrape failed: %s", repr(exc))

        logger.info(
            "Sarasota maturing commercial debt found: %d (scanned %d PDFs)",
            len(records),
            scanned,
        )
        return records

    def _fetch_sarasota_personal_commercial_balloon_clients(
        self,
        max_results: int,
    ) -> List[PropertyRecord]:
        """
        Sarasota-only targeted preset:
        commercial property, no current exemption, personal borrower,
        8%+ note rate, and balloon-style maturity within 6 months.
        """
        records: List[PropertyRecord] = []
        seen_instruments: set[str] = set()
        scan_limit = max(
            max_results * self.MATURING_SCAN_LIMIT_MULTIPLIER,
            self.MATURING_SCAN_MINIMUM,
        )
        scanned = 0
        today = datetime.now().date()
        maturity_cutoff = today + timedelta(days=self.TARGETED_BALLOON_WINDOW_DAYS)

        try:
            page = self.new_page()

            for year in self.MATURING_SEARCH_YEARS:
                if len(records) >= max_results or scanned >= scan_limit:
                    break

                try:
                    self._search_official_records(
                        page,
                        "MORTGAGE",
                        f"01/01/{year}",
                        f"12/31/{year}",
                    )
                    rows = self._parse_results(page)
                except Exception as exc:
                    if self._is_target_closed_error(exc):
                        logger.warning(
                            "Sarasota balloon: page closed mid-search for year %d, reopening",
                            year,
                        )
                        page = self._get_fresh_page(page)
                        try:
                            self._search_official_records(
                                page,
                                "MORTGAGE",
                                f"01/01/{year}",
                                f"12/31/{year}",
                            )
                            rows = self._parse_results(page)
                        except Exception as retry_exc:
                            logger.warning(
                                "Sarasota balloon: retry failed for year %d: %s",
                                year,
                                repr(retry_exc),
                            )
                            continue
                    else:
                        raise

                for row in rows:
                    if len(records) >= max_results or scanned >= scan_limit:
                        break

                    instrument_number = row.get("instrument_number", "").strip()
                    if not instrument_number or instrument_number in seen_instruments:
                        continue
                    seen_instruments.add(instrument_number)

                    pdf_bytes = self._download_clerk_pdf(
                        image_url=row.get("image_url", ""),
                        instrument_number=instrument_number,
                    )
                    if not pdf_bytes:
                        continue

                    scanned += 1
                    terms = self._extract_mortgage_pdf_terms(pdf_bytes)
                    maturity_dt = parse_record_date(terms.get("maturity_date", ""))
                    if not maturity_dt:
                        continue
                    maturity_date = maturity_dt.date()
                    if maturity_date < today or maturity_date > maturity_cutoff:
                        continue

                    borrower_name = terms.get("borrower_name", "").strip() or row.get("grantee", "")
                    if not borrower_name or not self._is_likely_personal_name(borrower_name):
                        continue

                    interest_rate = self._parse_percent(terms.get("interest_rate", ""))
                    if interest_rate < self.TARGETED_MIN_INTEREST_RATE:
                        continue

                    has_balloon_signal, balloon_reason = self._has_balloon_signal(
                        terms.get("pdf_text", "")
                    )
                    if not has_balloon_signal:
                        continue

                    record = PropertyRecord(
                        owner_name=borrower_name,
                        last_sale_date=row.get("rec_date", ""),
                        estimated_interest_rate=terms.get("interest_rate", ""),
                        county=self.county_name,
                        deed_type=row.get("instrument_type", ""),
                        lead_type=LeadType.BALLOON_PROSPECTS.value,
                        instrument_number=instrument_number,
                        lead_source="Sarasota Official Records + OCR",
                        notes=(
                            "Targeted Sarasota client profile: personal borrower, "
                            "commercial property, no current exemption, 8%+ note rate, "
                            "balloon-style maturity within 6 months"
                        ),
                    )
                    record = self._apply_clerk_pdf_terms(record, row, terms)
                    record = self._enrich_record_from_pa_owner_search(record, borrower_name)

                    if not record.property_type or not self._looks_commercial_property_type(
                        record.property_type
                    ):
                        continue

                    if not record.parcel_id:
                        continue
                    details = self._fetch_pa_details(record.parcel_id)
                    if not self._is_non_homestead_candidate(details):
                        continue
                    record.current_exemptions = details.get(
                        "current_exemptions",
                        record.current_exemptions,
                    )

                    note_bits = [record.notes] if record.notes else []
                    note_bits.append("Commercial signal: commercial-property-type")
                    note_bits.append(f"Balloon signal: {balloon_reason}")
                    note_bits.append(f"Current exemptions: ${record.current_exemptions or '0'}")
                    note_bits.append(f"Interest threshold met: {terms.get('interest_rate', '')}")
                    record.notes = " | ".join(dict.fromkeys([bit for bit in note_bits if bit]))
                    records.append(record)

            page.context.close()
        except Exception as exc:
            logger.error(
                "Sarasota targeted personal commercial balloon scrape failed: %s",
                repr(exc),
            )

        logger.info(
            "Sarasota targeted personal commercial balloon leads found: %d (scanned %d PDFs)",
            len(records),
            scanned,
        )
        return records

    def _fetch_balloon_prospects(self, max_results: int) -> List[PropertyRecord]:
        """Return the union of both Sarasota balloon prospect workflows."""
        merged: List[PropertyRecord] = []
        seen: Set[tuple[str, ...]] = set()

        for record in (
            self._fetch_maturing_commercial_debt(max_results)
            + self._fetch_sarasota_personal_commercial_balloon_clients(max_results)
        ):
            instrument = (record.instrument_number or "").strip()
            key: tuple[str, ...] = (
                ("instrument", instrument)
                if instrument
                else (
                    "fallback",
                    (record.owner_name or "").strip().upper(),
                    (record.property_address or "").strip().upper(),
                    (record.last_sale_date or "").strip(),
                )
            )
            if key in seen:
                continue
            seen.add(key)
            record.lead_type = LeadType.BALLOON_PROSPECTS.value
            merged.append(record)
            if len(merged) >= max_results:
                break
        return merged

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
                        lead_type=LeadType.BALLOON_PROSPECTS.value,
                    )
                    rec = self._enrich_record_from_pa(rec)
                    records.append(rec)

            page.context.close()
        except Exception as exc:
            logger.error("Sarasota past-financing scrape failed: %s", repr(exc))

        logger.info("Sarasota past-financing found: %d", len(records))
        return records
