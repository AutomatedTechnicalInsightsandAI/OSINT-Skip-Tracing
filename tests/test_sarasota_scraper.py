"""
Targeted tests for Sarasota result parsing and clerk PDF enrichment hooks.
"""

from __future__ import annotations

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
    monkeypatch.setattr(
        scraper,
        "_fetch_maturing_commercial_debt",
        lambda max_results: [
            PropertyRecord(
                owner_name="SUNCOAST OFFICE PARK LLC",
                county="Sarasota",
                lead_type=LeadType.BALLOON_PROSPECTS.value,
            )
        ],
    )
    monkeypatch.setattr(
        scraper,
        "_fetch_sarasota_personal_commercial_balloon_clients",
        lambda max_results: [
            PropertyRecord(
                owner_name="LISA K SNYDER",
                county="Sarasota",
                lead_type=LeadType.BALLOON_PROSPECTS.value,
            )
        ],
    )

    records = scraper.fetch_records(LeadType.BALLOON_PROSPECTS, max_results=5)

    assert len(records) == 2
    assert records[0].lead_type == LeadType.BALLOON_PROSPECTS.value
    assert records[1].lead_type == LeadType.BALLOON_PROSPECTS.value


def test_is_likely_personal_name_rejects_bank():
    scraper = SarasotaScraper(headless=True)

    assert scraper._is_likely_personal_name("BANK OF AMERICA NA") is False
    assert scraper._is_likely_personal_name("LISA K SNYDER") is True


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
