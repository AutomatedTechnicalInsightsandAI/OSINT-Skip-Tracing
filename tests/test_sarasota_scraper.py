"""
Targeted tests for Sarasota result parsing and clerk PDF enrichment hooks.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from scrapers.base_scraper import LeadType, PropertyRecord
from scrapers.sarasota_scraper import SarasotaScraper


RESULTS_HTML = """
<div id="ctl00_cphBody_rgCaseList">
  <table>
    <thead>
      <tr>
        <th>Image</th>
        <th>Instrument Number</th>
        <th>Book-Page</th>
        <th>Date Recorded</th>
        <th>Document Type</th>
        <th>Name</th>
        <th>Legal Description</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><a href="/viewTiff.aspx?intrnum=2026047868" target="_blank">View Image</a></td>
        <td>2026047868</td>
        <td>0-0</td>
        <td>04/13/2026</td>
        <td>MORTGAGE</td>
        <td>BANK OF AMERICA NA</td>
        <td>LT 48 WELLINGTON CHASE UN 1</td>
      </tr>
    </tbody>
  </table>
</div>
"""


class _FakePage:
    def content(self) -> str:
        return RESULTS_HTML


class _SearchPage:
    def __init__(self, *, load_raises: bool = False, selector_raises: bool = False):
        self.load_raises = load_raises
        self.selector_raises = selector_raises
        self.goto_calls = []
        self.fill_calls = []
        self.click_calls = []
        self.load_wait_calls = []
        self.selector_wait_calls = []

    def goto(self, url: str, **kwargs):
        self.goto_calls.append((url, kwargs))

    def fill(self, selector: str, value: str):
        self.fill_calls.append((selector, value))

    def click(self, selector: str):
        self.click_calls.append(selector)

    def wait_for_load_state(self, state: str, timeout: int | None = None):
        self.load_wait_calls.append((state, timeout))
        if self.load_raises:
            raise RuntimeError("load timeout")

    def wait_for_selector(self, selector: str, **kwargs):
        self.selector_wait_calls.append((selector, kwargs))
        if self.selector_raises:
            raise RuntimeError("selector timeout")


def test_parse_results_keeps_instrument_number_and_image_url():
    scraper = SarasotaScraper(headless=True)
    rows = scraper._parse_results(_FakePage())

    assert len(rows) == 1
    row = rows[0]
    assert row["instrument_number"] == "2026047868"
    assert row["image_url"].endswith("/viewTiff.aspx?intrnum=2026047868")
    assert row["instrument_type"] == "MORTGAGE"


def test_parse_results_ignores_nested_pager_headers():
    scraper = SarasotaScraper(headless=True)
    rows = scraper._parse_results(_FakePage())

    assert len(rows) == 1


def test_enrich_record_from_clerk_pdf_uses_ocr_terms(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF-sample")
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: {
            "instrument_number": "2026047868",
            "lender_name": "Bank of America, N. A",
            "credit_limit": "250000.00",
            "interest_rate": "8.75%",
            "maturity_date": "April 1, 2056",
            "doc_stamp_mortgage": "875.00",
            "intangible_tax": "500.00",
            "extraction_method": "ocr",
            "pdf_text": "sample",
        },
    )

    record = PropertyRecord(
        owner_name="Borrower",
        county="Sarasota",
        lead_type=LeadType.BALLOON_PROSPECTS.value,
        lead_source="Sarasota Official Records",
    )
    enriched = scraper._enrich_record_from_clerk_pdf(
        record,
        {
            "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2026047868",
            "instrument_number": "2026047868",
        },
    )

    assert enriched.instrument_number == "2026047868"
    assert enriched.lender_name == "Bank of America, N. A"
    assert enriched.maturity_date == "April 1, 2056"
    assert enriched.mtg_amt_at_purchase == "250000.00"
    assert enriched.estimated_interest_rate == "8.75%"
    assert enriched.pdf_extraction_method == "ocr"
    assert "Maturity Date: April 1, 2056" in enriched.notes


def test_apply_clerk_pdf_terms_uses_doc_stamp_fallback_and_cleans_owner_name():
    scraper = SarasotaScraper(headless=True)
    record = PropertyRecord(owner_name="Original Owner", county="Sarasota")

    enriched = scraper._apply_clerk_pdf_terms(
        record,
        {
            "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2026047868",
            "instrument_number": "2026047868",
        },
        {
            "instrument_number": "2026047868",
            "borrower_name": "SUNCOAST\nOFFICE PARTNERS LLC",
            "doc_stamp_mortgage": "980.00",
            "pdf_text": "",
        },
    )

    assert enriched.owner_name == "SUNCOAST OFFICE PARTNERS LLC"
    assert enriched.mtg_amt_at_purchase == "280000.00"
    assert enriched.mtg_amt_source == "Sarasota Clerk OCR: Estimated principal from doc stamp"


def test_is_likely_commercial_mortgage_rejects_consumer_heloc():
    scraper = SarasotaScraper(headless=True)

    is_commercial, reason = scraper._is_likely_commercial_mortgage(
        borrower_name="LISA K SNYDER",
        pdf_text="FLORIDA HOME EQUITY LINE OF CREDIT MORTGAGE",
        property_type="Single Family Residential",
    )

    assert is_commercial is False
    assert reason == "consumer-doc-phrase"


def test_is_likely_commercial_mortgage_accepts_entity_borrower():
    scraper = SarasotaScraper(headless=True)

    is_commercial, reason = scraper._is_likely_commercial_mortgage(
        borrower_name="SUNCOAST OFFICE PARK LLC",
        pdf_text="Mortgage and security instrument.",
        property_type="",
    )

    assert is_commercial is True
    assert reason == "entity-borrower"


def test_fetch_records_routes_balloon_prospects_union(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()

    pa_lookup = {
        "AMY M PINTUS": [
            {
                "Account #": "0123456789",
                "Situs Address": "10 MAIN ST, SARASOTA FL 34230",
                "Mailing Address": "PO BOX 1, SARASOTA FL 34230",
                "Owner 1": "AMY M PINTUS",
                "Owner 2": "",
                "Owner 3": "",
                "Just Value": "350000",
                "Assessed Value": "300000",
                "Taxable Value": "300000",
                "Description": "Single Family",
            }
        ]
    }
    monkeypatch.setattr(scraper, "_build_pa_bulk_lookup", lambda: (pa_lookup, list(pa_lookup.values())))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021007957",
                "image_url": "",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "BANK OF AMERICA NA\nAMY M PINTUS",
            }
        ],
    )

    records = scraper.fetch_records(LeadType.BALLOON_PROSPECTS, max_results=5)

    assert len(records) == 1
    assert records[0].lead_type == LeadType.BALLOON_PROSPECTS.value
    assert records[0].owner_name == "AMY M PINTUS"
    assert records[0].instrument_number == "2021007957"
    assert records[0].lead_source == "Sarasota Clerk Index + PA Bulk CSV"


def test_is_likely_personal_name_rejects_bank():
    scraper = SarasotaScraper(headless=True)

    assert scraper._is_likely_personal_name("BANK OF AMERICA NA") is False
    assert scraper._is_likely_personal_name("LISA K SNYDER") is True


def test_extract_balloon_balance_from_sarasota_maturity_language():
    scraper = SarasotaScraper(headless=True)
    text = (
        "BALLOON PURCHASE MONEY MORTGAGE\n"
        "THIS IS A BALLOON MORTGAGE AND THE FINAL PRINCIPAL PAYMENT OR THE "
        "PRINCIPAL BALANCE DUE UPON MATURITY IS $280,000.00, TOGETHER WITH ACCRUED INTEREST."
    )

    assert scraper._extract_balloon_balance(text) == 280000.0
    assert scraper._has_balloon_signal(text)[0] is True


def test_fetch_maturing_commercial_debt_skips_below_min_balloon_balance(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()
    maturity_date = "04/01/2026"

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021000001",
                "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2021000001",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "SUNCOAST OFFICE PARK LLC",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF")
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: True)
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: {
            "borrower_name": "SUNCOAST OFFICE PARK LLC",
            "maturity_date": maturity_date,
            "pdf_text": (
                "FINAL PRINCIPAL PAYMENT OR THE PRINCIPAL BALANCE DUE UPON MATURITY "
                "IS $79,999.00"
            ),
        },
    )
    monkeypatch.setattr(scraper, "_enrich_record_from_pa_owner_search", lambda record, _name: record)
    monkeypatch.setattr(
        scraper,
        "_is_likely_commercial_mortgage",
        lambda **_kwargs: (True, "commercial-doc-phrase"),
    )

    records = scraper._fetch_maturing_commercial_debt(max_results=5)

    assert records == []
    assert page.context.closed is True


def test_fetch_personal_commercial_balloon_client_adds_balloon_balance_note(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()
    maturity_date = "06/15/2027"

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021000002",
                "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2021000002",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "LISA K SNYDER",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF")
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: True)
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: {
            "borrower_name": "LISA K SNYDER",
            "maturity_date": maturity_date,
            "interest_rate": "3.25%",
            "pdf_text": (
                "BALLOON PURCHASE MONEY MORTGAGE. THE FINAL PRINCIPAL PAYMENT OR THE "
                "PRINCIPAL BALANCE DUE UPON MATURITY IS $180,000.00."
            ),
        },
    )

    def _enrich(record, _name):
        record.property_type = "Commercial Office"
        record.parcel_id = "1234567890"
        return record

    monkeypatch.setattr(scraper, "_enrich_record_from_pa_owner_search", _enrich)
    monkeypatch.setattr(
        scraper,
        "_fetch_pa_details",
        lambda _parcel_id: {"has_current_exemption": "false", "current_exemptions": "0"},
    )

    records = scraper._fetch_sarasota_personal_commercial_balloon_clients(max_results=5)

    assert len(records) == 1
    assert "Balloon Balance: $180,000" in records[0].notes
    assert "Commercial Borrower: False" in records[0].notes
    assert page.context.closed is True


def test_search_official_records_uses_load_timeout_and_results_selector(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _SearchPage()
    monkeypatch.setattr(scraper, "_select_doc_type", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scraper, "_fill_party_name", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scraper, "sleep", lambda: None)
    monkeypatch.setattr(scraper, "random_scroll", lambda _page: None)

    scraper._search_official_records(
        page,
        doc_type="MORTGAGE",
        date_from="01/01/2024",
        date_to="12/31/2024",
    )

    assert page.goto_calls == [
        (scraper.CLERK_URL, {"wait_until": "domcontentloaded", "timeout": 30_000})
    ]
    assert page.load_wait_calls == [("load", 15_000)]
    assert page.selector_wait_calls == [
        (
            "#ctl00_cphBody_rgCaseList table, table",
            {"timeout": 10_000, "state": "visible"},
        )
    ]


def test_search_official_records_ignores_load_and_selector_wait_timeouts(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _SearchPage(load_raises=True, selector_raises=True)
    monkeypatch.setattr(scraper, "_select_doc_type", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scraper, "_fill_party_name", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scraper, "sleep", lambda: None)
    monkeypatch.setattr(scraper, "random_scroll", lambda _page: None)

    scraper._search_official_records(
        page,
        doc_type="MORTGAGE",
        date_from="01/01/2024",
        date_to="12/31/2024",
    )

    assert page.click_calls == ["#ctl00_cphBody_bSearch_input"]


class _FakeContext:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeLoopPage:
    def __init__(self):
        self.context = _FakeContext()
        self.goto_calls = []

    def goto(self, url: str, **kwargs):
        self.goto_calls.append((url, kwargs))


class _FakeImagePage:
    def __init__(self, context):
        self.context = context
        self.default_timeouts = []
        self.goto_calls = []
        self.selector_wait_calls = []
        self.timeout_wait_calls = []

    def set_default_timeout(self, timeout: int):
        self.default_timeouts.append(timeout)

    def goto(self, url: str, **kwargs):
        self.goto_calls.append((url, kwargs))

    def wait_for_selector(self, selector: str, **kwargs):
        self.selector_wait_calls.append((selector, kwargs))

    def wait_for_timeout(self, timeout: int):
        self.timeout_wait_calls.append(timeout)


class _FakeImageContext:
    def __init__(self):
        self.closed = False
        self.page = _FakeImagePage(self)

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class _FakeImageBrowser:
    def __init__(self):
        self.contexts: list[_FakeImageContext] = []

    def new_context(self):
        context = _FakeImageContext()
        self.contexts.append(context)
        return context


@pytest.mark.parametrize(
    "method_name",
    [
        "_fetch_balloon_balance_leads",
        "_fetch_maturing_commercial_debt",
        "_fetch_sarasota_personal_commercial_balloon_clients",
    ],
)
def test_balloon_flows_skip_full_extraction_when_first_page_has_no_signal(monkeypatch, method_name):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021000009",
                "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2021000009",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "SUNCOAST PARTNERS LLC",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF")
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: False)
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: (_ for _ in ()).throw(AssertionError("full extraction should be skipped")),
    )

    records = getattr(scraper, method_name)(max_results=5)

    assert records == []
    assert page.context.closed is True


@pytest.mark.parametrize(
    "method_name",
    [
        "_fetch_balloon_balance_leads",
        "_fetch_maturing_commercial_debt",
        "_fetch_sarasota_personal_commercial_balloon_clients",
    ],
)
def test_balloon_flows_open_view_image_in_throwaway_context(monkeypatch, method_name):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()
    image_browser = _FakeImageBrowser()
    scraper._browser = image_browser

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021000009",
                "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2021000009",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "SUNCOAST PARTNERS LLC",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF")
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: False)
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: (_ for _ in ()).throw(AssertionError("full extraction should be skipped")),
    )

    records = getattr(scraper, method_name)(max_results=5)

    assert records == []
    assert page.goto_calls == []
    assert len(image_browser.contexts) == 1
    image_ctx = image_browser.contexts[0]
    assert image_ctx.page.default_timeouts == [20_000]
    assert image_ctx.page.goto_calls[0][0].endswith("intrnum=2021000009")
    assert image_ctx.page.selector_wait_calls == [
        ("img, embed, object, iframe", {"timeout": 5_000})
    ]
    assert image_ctx.page.timeout_wait_calls == [3_000]
    assert image_ctx.closed is True
    assert page.context.closed is True


def test_fetch_balloon_balance_leads_filters_for_2026_or_2027_and_populates_balance(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()
    maturity_date = "04/01/2027"

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021007957",
                "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2021007957",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "AMY M PINTUS",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF")
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: True)
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: {
            "instrument_number": "2021007957",
            "borrower_name": "AMY M PINTUS",
            "maturity_date": maturity_date,
            "pdf_text": (
                "THIS IS A BALLOON MORTGAGE AND THE FINAL PRINCIPAL PAYMENT OR THE "
                "PRINCIPAL BALANCE DUE UPON MATURITY IS $280,000.00"
            ),
        },
    )
    monkeypatch.setattr(scraper, "_enrich_record_from_pa_owner_search", lambda record, _name: record)

    records = scraper._fetch_balloon_balance_leads(max_results=5)

    assert len(records) == 1
    assert records[0].balloon_balance == "280000"
    assert records[0].instrument_number == "2021007957"
    assert page.goto_calls == []
    assert page.context.closed is True


def test_fetch_balloon_balance_leads_skips_non_2026_2027_maturity(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021007958",
                "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2021007958",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "AMY M PINTUS",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF")
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: True)
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: {
            "instrument_number": "2021007958",
            "borrower_name": "AMY M PINTUS",
            "maturity_date": "04/01/2028",
            "pdf_text": (
                "THIS IS A BALLOON MORTGAGE AND THE FINAL PRINCIPAL PAYMENT OR THE "
                "PRINCIPAL BALANCE DUE UPON MATURITY IS $280,000.00"
            ),
        },
    )
    monkeypatch.setattr(scraper, "_enrich_record_from_pa_owner_search", lambda record, _name: record)

    records = scraper._fetch_balloon_balance_leads(max_results=5)

    assert records == []
    assert page.context.closed is True


def test_fetch_balloon_balance_leads_respects_balloon_scan_target(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()
    download_calls: list[str] = []

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
    monkeypatch.setattr(scraper, "BALLOON_SCAN_TARGET", 1)
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021007001",
                "image_url": "",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "FIRST BORROWER",
            },
            {
                "instrument_number": "2021007002",
                "image_url": "",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "SECOND BORROWER",
            },
        ],
    )

    def _download(**kwargs):
        download_calls.append(kwargs["instrument_number"])
        return b"%PDF"

    monkeypatch.setattr(scraper, "_download_clerk_pdf", _download)
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: True)
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: {
            "borrower_name": "SAMPLE BORROWER",
            "maturity_date": "04/01/2027",
            "pdf_text": (
                "THIS IS A BALLOON MORTGAGE AND THE FINAL PRINCIPAL PAYMENT OR THE "
                "PRINCIPAL BALANCE DUE UPON MATURITY IS $280,000.00"
            ),
        },
    )
    monkeypatch.setattr(scraper, "_enrich_record_from_pa_owner_search", lambda record, _name: record)

    records = scraper._fetch_balloon_balance_leads(max_results=5)

    assert len(records) == 1
    assert download_calls == ["2021007001"]
    assert page.context.closed is True


def test_balloon_flows_reopen_page_after_target_closed(monkeypatch):
    for method_name in (
        "_fetch_maturing_commercial_debt",
        "_fetch_sarasota_personal_commercial_balloon_clients",
    ):
        scraper = SarasotaScraper(headless=True)
        first_page = _FakeLoopPage()
        second_page = _FakeLoopPage()
        pages = iter([first_page, second_page])
        search_calls: list[_FakeLoopPage] = []

        monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
        monkeypatch.setattr(scraper, "new_page", lambda: next(pages))

        def _fake_search(page, *_args, **_kwargs):
            search_calls.append(page)
            if len(search_calls) == 1:
                raise RuntimeError(
                    "TargetClosedError('Page.evaluate: Target page, context or browser has been closed')"
                )

        monkeypatch.setattr(scraper, "_search_official_records", _fake_search)
        monkeypatch.setattr(scraper, "_parse_results", lambda _page: [])

        records = getattr(scraper, method_name)(max_results=1)

        assert records == []
        assert search_calls == [first_page, second_page]
        assert first_page.context.closed is True
        assert second_page.context.closed is True


def test_fetch_maturing_commercial_debt_adds_commercial_borrower_flag(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()
    maturity_dt = datetime(2027, 4, 18)
    day = maturity_dt.day
    suffix = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    maturity_date = f"to be due by {day}{suffix} day of {maturity_dt.strftime('%B, %Y')} (Maturity Date)"

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2021,))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2021000003",
                "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2021000003",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "SUNCOAST PARTNERS LLC",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF")
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: True)
    monkeypatch.setattr(
        scraper,
        "_extract_mortgage_pdf_terms",
        lambda _pdf: {
            "borrower_name": "SUNCOAST PARTNERS LLC",
            "maturity_date": maturity_date,
            "pdf_text": (
                "THIS IS A BALLOON MORTGAGE. THE FINAL PRINCIPAL PAYMENT OR THE "
                "PRINCIPAL BALANCE DUE UPON MATURITY IS $180,000.00."
            ),
        },
    )
    monkeypatch.setattr(scraper, "_enrich_record_from_pa_owner_search", lambda record, _name: record)
    monkeypatch.setattr(
        scraper,
        "_is_likely_commercial_mortgage",
        lambda **_kwargs: (True, "entity-borrower"),
    )

    records = scraper._fetch_maturing_commercial_debt(max_results=5)

    assert len(records) == 1
    assert "Commercial Borrower: True" in records[0].notes


def test_classify_mod_lead_priority_heloc_over_other_signals():
    strategy = SarasotaScraper._classify_mod_lead(
        owner_name="SUNCOAST LIVING TRUST",
        property_address="10 MAIN ST",
        mailing_address="PO BOX 20",
        is_heloc=True,
        maturity_date="November 10, 2027",
        has_balloon_signal=True,
        balloon_balance=95000.0,
    )
    assert strategy == "HELOC – Review Credit Limit & Terms"


def test_classify_mod_lead_cashout_refi_for_zero_purchase_mortgage():
    strategy = SarasotaScraper._classify_mod_lead(
        owner_name="ANY OWNER",
        property_address="10 MAIN ST",
        mailing_address="10 MAIN ST",
        is_heloc=False,
        maturity_date="",
        has_balloon_signal=False,
        balloon_balance=0.0,
        mtg_amt_at_purchase="0",
        sale_price="450000",
        just_value="500000",
        modified_principal="300000",
    )
    assert strategy == "Cash-Out Refi Candidate – Equity Available"


def test_classify_mod_lead_cashout_refi_for_low_ltv():
    strategy = SarasotaScraper._classify_mod_lead(
        owner_name="ANY OWNER",
        property_address="10 MAIN ST",
        mailing_address="10 MAIN ST",
        is_heloc=False,
        maturity_date="",
        has_balloon_signal=False,
        balloon_balance=0.0,
        mtg_amt_at_purchase="180000",
        sale_price="400000",
        just_value="",
        modified_principal="250000",
    )
    assert strategy == "Cash-Out Refi Candidate – Equity Available"


def test_fetch_mortgage_mod_leads_extracts_and_classifies(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()
    image_browser = _FakeImageBrowser()
    scraper._browser = image_browser

    monkeypatch.setattr(scraper, "MATURING_SEARCH_YEARS", (2024,))
    monkeypatch.setattr(scraper, "BALLOON_SCAN_TARGET", 5)
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _page: [
            {
                "instrument_number": "2024001001",
                "image_url": "https://secure.sarasotaclerk.com/viewTiff.aspx?intrnum=2024001001",
                "instrument_type": "MORTGAGE MOD AGREEMT",
                "rec_date": "04/01/2024",
                "grantee": "SUNCOAST LIVING TRUST",
            }
        ],
    )
    monkeypatch.setattr(scraper, "_download_clerk_pdf", lambda **_kwargs: b"%PDF")
    monkeypatch.setattr("scrapers.sarasota_scraper.is_balloon_mortgage_first_page", lambda _pdf: False)
    monkeypatch.setattr(
        "scrapers.sarasota_scraper.extract_pdf_text",
        lambda *_args, **_kwargs: type("Extraction", (), {"text": "MODIFICATION AGREEMENT", "method": "text"})(),
    )
    monkeypatch.setattr(
        "scrapers.sarasota_scraper.extract_mod_agreement_info",
        lambda _pdf: type(
            "ModInfo",
            (),
            {
                "borrower_name": "SUNCOAST LIVING TRUST",
                "property_address": "10 MAIN ST",
                "instrument_number": "2024001001",
                "modified_principal": "280500.25",
                "interest_rate": "7.25%",
                "rate_type": "Fixed",
                "maturity_date": "November 10, 2027",
                "is_heloc": False,
                "credit_limit": "350000.00",
                "balloon_balance": 95000.0,
                "has_balloon_signal": True,
                "trust_keywords_found": ["TRUST"],
                "extraction_method": "ocr",
                "extracted_text": "sample",
            },
        )(),
    )

    def _enrich(record, _name):
        record.mailing_address = "PO BOX 20"
        return record

    monkeypatch.setattr(scraper, "_enrich_record_from_pa_owner_search", _enrich)

    records = scraper._fetch_mortgage_mod_leads(max_results=5)

    assert len(records) == 1
    assert records[0].instrument_number == "2024001001"
    assert records[0].modified_principal == "280500.25"
    assert records[0].sales_strategy == "Balloon Due: November 10, 2027"
    assert records[0].trust_keywords == "TRUST"
    assert len(image_browser.contexts) == 1
    assert image_browser.contexts[0].closed is True


# ---------------------------------------------------------------------------
# Tests for the fast Clerk-index + PA-bulk-CSV helpers (no PDF / no OCR)
# ---------------------------------------------------------------------------

def test_extract_borrower_from_clerk_name_cell_strips_lender_lines():
    scraper = SarasotaScraper(headless=True)

    # Personal borrower after a bank line
    result = scraper._extract_borrower_from_clerk_name_cell(
        "FIRST STATE BANK\nSMITH JOHN A"
    )
    assert result == "SMITH JOHN A"

    # Two personal borrowers after a federal savings line
    result = scraper._extract_borrower_from_clerk_name_cell(
        "COAST FEDERAL SAVINGS\nHECHT LEONARD\nHECHT RHONA"
    )
    assert result == "HECHT LEONARD & HECHT RHONA"

    # Entire cell is a lender — returns empty string
    result = scraper._extract_borrower_from_clerk_name_cell("BARNETT BANK SW FLORIDA")
    assert result == ""

    # No lender line at all — pass through unchanged
    result = scraper._extract_borrower_from_clerk_name_cell("MCGREGOR CHARLES W")
    assert result == "MCGREGOR CHARLES W"


def test_match_borrower_to_pa_row_exact_substring():
    scraper = SarasotaScraper(headless=True)
    pa_row = {
        "Account #": "0011223344",
        "Situs Address": "100 OAK AVE",
        "Mailing Address": "PO BOX 5",
        "Owner 1": "MCGREGOR CHARLES W",
        "Owner 2": "MCGREGOR DORIS M",
        "Owner 3": "",
        "Just Value": "400000",
        "Assessed Value": "380000",
        "Taxable Value": "380000",
        "Description": "Single Family",
    }
    pa_lookup = {scraper._normalize_owner_match_text("MCGREGOR CHARLES W MCGREGOR DORIS M"): [pa_row]}

    result = scraper._match_borrower_to_pa_row("MCGREGOR CHARLES W & MCGREGOR DORIS M", pa_lookup)
    assert result is pa_row


def test_match_borrower_to_pa_row_token_overlap_fallback():
    scraper = SarasotaScraper(headless=True)
    pa_row = {
        "Account #": "9988776655",
        "Situs Address": "200 PINE ST",
        "Mailing Address": "PO BOX 9",
        "Owner 1": "PINTUS AMY M",
        "Owner 2": "",
        "Owner 3": "",
        "Just Value": "300000",
        "Assessed Value": "280000",
        "Taxable Value": "280000",
        "Description": "Condo",
    }
    pa_lookup = {scraper._normalize_owner_match_text("PINTUS AMY M"): [pa_row]}

    # Borrower name differs slightly but shares ≥2 tokens
    result = scraper._match_borrower_to_pa_row("AMY M PINTUS", pa_lookup)
    assert result is pa_row


def test_match_borrower_to_pa_row_no_match_returns_none():
    scraper = SarasotaScraper(headless=True)
    pa_lookup = {scraper._normalize_owner_match_text("COMPLETELY DIFFERENT NAME"): [{"Owner 1": "X"}]}
    result = scraper._match_borrower_to_pa_row("NOBODY HERE", pa_lookup)
    assert result is None


def test_fetch_balloon_prospects_builds_records_from_clerk_and_pa(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()

    pa_row = {
        "Account #": "1234567890",
        "Situs Address": "999 PALM DR SARASOTA FL 34230",
        "Mailing Address": "PO BOX 42 SARASOTA FL 34230",
        "Owner 1": "AMY M PINTUS",
        "Owner 2": "",
        "Owner 3": "",
        "Just Value": "410000",
        "Assessed Value": "400000",
        "Taxable Value": "400000",
        "Description": "Single Family",
    }
    pa_lookup = {scraper._normalize_owner_match_text("AMY M PINTUS"): [pa_row]}

    monkeypatch.setattr(scraper, "_build_pa_bulk_lookup", lambda: (pa_lookup, [pa_row]))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _p: [
            {
                "instrument_number": "2021007957",
                "image_url": "",
                "instrument_type": "MORTGAGE",
                "rec_date": "04/01/2021",
                "grantee": "BANK OF AMERICA NA\nAMY M PINTUS",
            }
        ],
    )

    records = scraper._fetch_balloon_prospects(max_results=5)

    assert len(records) == 1
    r = records[0]
    assert r.owner_name == "AMY M PINTUS"
    assert r.lead_type == LeadType.BALLOON_PROSPECTS.value
    assert r.lead_source == "Sarasota Clerk Index + PA Bulk CSV"
    assert r.absentee_owner == "True"
    assert "Est." in r.maturity_date
    assert "2026" in r.maturity_date  # rec_year 2021 + 5
    assert r.property_address == "999 PALM DR SARASOTA FL 34230"
    assert page.context.closed is True


def test_fetch_balloon_prospects_skips_institutional_borrowers(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()

    monkeypatch.setattr(scraper, "_build_pa_bulk_lookup", lambda: ({}, []))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _p: [
            {
                "instrument_number": "2020001111",
                "image_url": "",
                "instrument_type": "MORTGAGE",
                "rec_date": "06/01/2020",
                # Both lines are banks — borrower extraction returns empty
                "grantee": "FIRST STATE BANK\nNATIONAL FEDERAL SAVINGS",
            }
        ],
    )

    records = scraper._fetch_balloon_prospects(max_results=5)
    assert records == []
    assert page.context.closed is True


def test_fetch_balloon_prospects_creates_minimal_record_when_no_pa_match(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()

    monkeypatch.setattr(scraper, "_build_pa_bulk_lookup", lambda: ({}, []))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _p: [
            {
                "instrument_number": "2019005000",
                "image_url": "",
                "instrument_type": "MORTGAGE",
                "rec_date": "03/15/2019",
                "grantee": "BARNETT BANK SW FLORIDA\nSMITH JOHN A",
            }
        ],
    )

    records = scraper._fetch_balloon_prospects(max_results=5)

    # Record still created even without a PA match
    assert len(records) == 1
    r = records[0]
    assert r.owner_name == "SMITH JOHN A"
    assert r.property_address == ""  # no PA match
    assert r.absentee_owner == ""
    assert r.lead_source == "Sarasota Clerk Index + PA Bulk CSV"
    assert page.context.closed is True


def test_fetch_mortgage_mod_standalone_no_pdf(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    page = _FakeLoopPage()

    pa_row = {
        "Account #": "5544332211",
        "Situs Address": "50 SHORE DR SARASOTA FL",
        "Mailing Address": "PO BOX 77 SARASOTA FL",
        "Owner 1": "HECHT LEONARD",
        "Owner 2": "HECHT RHONA",
        "Owner 3": "",
        "Just Value": "620000",
        "Assessed Value": "600000",
        "Taxable Value": "600000",
        "Description": "Residential",
    }
    pa_lookup = {
        scraper._normalize_owner_match_text("HECHT LEONARD HECHT RHONA"): [pa_row]
    }

    monkeypatch.setattr(scraper, "_build_pa_bulk_lookup", lambda: (pa_lookup, [pa_row]))
    monkeypatch.setattr(scraper, "new_page", lambda: page)
    monkeypatch.setattr(scraper, "_search_official_records", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        scraper,
        "_parse_results",
        lambda _p: [
            {
                "instrument_number": "2024009876",
                "image_url": "",
                "instrument_type": "MORTGAGE MOD AGREEMT",
                "rec_date": "07/10/2024",
                "grantee": "COAST FEDERAL SAVINGS\nHECHT LEONARD\nHECHT RHONA",
            }
        ],
    )

    records = scraper._fetch_mortgage_mod_standalone(max_results=5)

    assert len(records) == 1
    r = records[0]
    assert r.owner_name == "HECHT LEONARD & HECHT RHONA"
    assert r.lead_type == LeadType.MORTGAGE_MOD.value
    assert r.lead_source == "Sarasota Clerk Index + PA Bulk CSV"
    assert r.instrument_number == "2024009876"
    assert r.absentee_owner == "True"
    assert "prime refi candidate" in r.notes
    assert r.maturity_date == ""
    assert page.context.closed is True


def test_build_pa_bulk_lookup_caches_result(monkeypatch):
    scraper = SarasotaScraper(headless=True)
    call_count = 0

    def _fake_lookup():
        nonlocal call_count
        call_count += 1
        return {"KEY": [{"Owner 1": "TEST"}]}, [{"Owner 1": "TEST"}]

    # Pre-populate cache directly
    scraper._pa_bulk_lookup_cache = ({"CACHED": [{"Owner 1": "CACHED"}]}, [{"Owner 1": "CACHED"}])

    result_lookup, result_rows = scraper._build_pa_bulk_lookup()

    # Should return the cached value without making any HTTP call
    assert "CACHED" in result_lookup
    assert call_count == 0
