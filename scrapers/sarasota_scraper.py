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
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from urllib.parse import urlparse, parse_qs
import requests

from scrapers.base_scraper import (
    BaseScraper,
    LeadType,
    PropertyRecord,
    estimate_interest_rate,
    parse_record_date,
)

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
    CASHOUT_LOOKBACK_DAYS = 183
    CASHOUT_MIN_SALE_PRICE = 250_000
    MORTGAGE_LOOKBACK_DAYS = 7
    MORTGAGE_LOOKAHEAD_DAYS = 21
    CASHOUT_CANDIDATE_MULTIPLIER = 2
    CASHOUT_MIN_CANDIDATES_TO_CHECK = 75
    TARGET_QUALIFICATION_CODES = {"01"}
    NON_PERSON_TOKENS = {"TRUST", "TR", "TTEE", "TRUSTEE", "LLC", "INC", "CORP", "CORPORATION", "LP", "LTD", "LC", "CO"}
    CACHE_PATH = Path(".cache") / "sarasota_mortgage_lookup.json"

    def __init__(self, headless: bool = False, timeout_ms: int = 30_000):
        super().__init__(headless=headless, timeout_ms=timeout_ms)
        self._mortgage_lookup_cache = self._load_mortgage_cache()

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

        if lead_type == LeadType.CASHOUT_REFI:
            return self._fetch_cashout_refi(max_results)
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
        party_last: str = "",
        party_first: str = "",
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
            page.wait_for_load_state("networkidle")
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

        headers = [self.safe_text(th).lower() for th in table.find_all("th")]
        header_index = {header: idx for idx, header in enumerate(headers)}

        if "document type" in header_index and "date recorded" in header_index:
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < len(header_index):
                    continue
                rows_data.append(
                    {
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

    def _fetch_cashout_refi(self, max_results: int) -> List[PropertyRecord]:
        """
        Find recent Sarasota purchases over $250k with no matching mortgage
        recorded at purchase, which are strong cash-out refinance prospects.
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
        """Use Sarasota PA advanced search/export for recent sales over the price floor."""
        sale_to = datetime.now()
        sale_from = sale_to - timedelta(days=self.CASHOUT_LOOKBACK_DAYS)
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
        logger.info("Sarasota PA export returned %d recent high-price sales", len(sales))
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
