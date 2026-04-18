from __future__ import annotations

from scrapers.broward_scraper import BrowardScraper
from scrapers.miami_dade_scraper import MiamiDadeScraper


class _BrowardPage:
    def __init__(self, *, load_raises: bool = False):
        self.load_raises = load_raises
        self.goto_calls = []
        self.load_wait_calls = []

    def goto(self, url: str, **kwargs):
        self.goto_calls.append((url, kwargs))

    def wait_for_load_state(self, state: str, timeout: int | None = None):
        self.load_wait_calls.append((state, timeout))
        if self.load_raises:
            raise RuntimeError("load timeout")

    def content(self) -> str:
        return "<html></html>"


class _MiamiPage:
    def __init__(self, *, load_raises: bool = False):
        self.load_raises = load_raises
        self.goto_calls = []
        self.load_wait_calls = []
        self.select_calls = []
        self.fill_calls = []
        self.click_calls = []

    def goto(self, url: str, **kwargs):
        self.goto_calls.append((url, kwargs))

    def select_option(self, selector: str, value: str):
        self.select_calls.append((selector, value))

    def fill(self, selector: str, value: str):
        self.fill_calls.append((selector, value))

    def click(self, selector: str):
        self.click_calls.append(selector)

    def wait_for_load_state(self, state: str, timeout: int | None = None):
        self.load_wait_calls.append((state, timeout))
        if self.load_raises:
            raise RuntimeError("load timeout")

    def content(self) -> str:
        return "<html></html>"


def test_broward_clerk_instrument_search_uses_load_timeout_wait(monkeypatch):
    scraper = BrowardScraper(headless=True)
    page = _BrowardPage()
    monkeypatch.setattr(scraper, "sleep", lambda: None)
    monkeypatch.setattr(scraper, "random_scroll", lambda _page: None)
    monkeypatch.setattr(scraper, "parse_html", lambda html: html)

    html = scraper._clerk_instrument_search(
        page, "WD", date_from="01/01/2024", date_to="12/31/2024"
    )

    assert "InstrumentType=WD" in page.goto_calls[0][0]
    assert page.goto_calls[0][1] == {"wait_until": "domcontentloaded"}
    assert page.load_wait_calls == [("load", 15_000)]
    assert html == "<html></html>"


def test_broward_clerk_instrument_search_ignores_load_wait_timeout(monkeypatch):
    scraper = BrowardScraper(headless=True)
    page = _BrowardPage(load_raises=True)
    monkeypatch.setattr(scraper, "sleep", lambda: None)
    monkeypatch.setattr(scraper, "random_scroll", lambda _page: None)
    monkeypatch.setattr(scraper, "parse_html", lambda html: html)

    html = scraper._clerk_instrument_search(page, "WD")

    assert page.load_wait_calls == [("load", 15_000)]
    assert html == "<html></html>"


def test_miami_clerk_search_uses_load_timeout_wait(monkeypatch):
    scraper = MiamiDadeScraper(headless=True)
    page = _MiamiPage()
    monkeypatch.setattr(scraper, "sleep", lambda: None)
    monkeypatch.setattr(scraper, "random_scroll", lambda _page: None)
    monkeypatch.setattr(scraper, "parse_html", lambda html: html)

    html = scraper._clerk_search(page, instrument_type_filter="MT", start_year=2023)

    assert page.goto_calls == [(scraper.CLERK_URL, {"wait_until": "domcontentloaded"})]
    assert page.load_wait_calls == [("load", 15_000)]
    assert page.select_calls == [('select[name="InstrumentType"]', "MT")]
    assert page.fill_calls == [
        ('input[name="StartDate"]', "01/01/2023"),
        ('input[name="EndDate"]', "12/31/2024"),
    ]
    assert page.click_calls == ['input[type="submit"]']
    assert html == "<html></html>"


def test_miami_clerk_search_ignores_load_wait_timeout(monkeypatch):
    scraper = MiamiDadeScraper(headless=True)
    page = _MiamiPage(load_raises=True)
    monkeypatch.setattr(scraper, "sleep", lambda: None)
    monkeypatch.setattr(scraper, "random_scroll", lambda _page: None)
    monkeypatch.setattr(scraper, "parse_html", lambda html: html)

    html = scraper._clerk_search(page, instrument_type_filter="MT")

    assert page.load_wait_calls == [("load", 15_000)]
    assert html == "<html></html>"
