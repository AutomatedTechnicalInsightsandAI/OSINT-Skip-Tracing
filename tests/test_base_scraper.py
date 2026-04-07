"""
Tests for scrapers/base_scraper.py — pure-logic functions that don't require
a live browser or network connection.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from scrapers.base_scraper import (
    BaseScraper,
    LeadType,
    PropertyRecord,
    estimate_interest_rate,
    is_high_rate_era,
    is_older_than_years,
)


# ---------------------------------------------------------------------------
# LeadType enum
# ---------------------------------------------------------------------------


def test_lead_type_values():
    assert LeadType.FLIPPER.value == "Fix & Flip Investors"
    assert LeadType.HIGH_INTEREST.value == "High Interest / High Equity (DSCR Prospects)"
    assert LeadType.PAST_FINANCING.value == "Past Financing (Satisfied Mortgage / Certificate of Title)"


# ---------------------------------------------------------------------------
# PropertyRecord.to_dict()
# ---------------------------------------------------------------------------


def test_property_record_to_dict_keys():
    rec = PropertyRecord(
        owner_name="John Smith",
        property_address="123 Main St",
        mailing_address="PO Box 1",
        last_sale_date="01/15/2023",
        estimated_interest_rate="~6.81%",
        scraped_emails="john@example.com",
        county="Sarasota",
        lead_type=LeadType.FLIPPER.value,
    )
    d = rec.to_dict()
    required = [
        "Owner Name",
        "Property Address",
        "Mailing Address",
        "Last Sale Date",
        "Estimated Interest Rate",
        "Scraped Emails",
    ]
    for col in required:
        assert col in d, f"Missing required column: {col}"


def test_property_record_to_dict_values():
    rec = PropertyRecord(owner_name="Jane Doe", county="Broward")
    d = rec.to_dict()
    assert d["Owner Name"] == "Jane Doe"
    assert d["County"] == "Broward"


# ---------------------------------------------------------------------------
# estimate_interest_rate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "date_str, expected_fragment",
    [
        ("01/15/2022", "5.34"),
        ("06/30/2023", "6.81"),
        ("2021-03-01", "2.96"),
        ("March 15, 2020", "3.11"),
        ("", "Unknown"),
        ("not-a-date", "Unknown"),
    ],
)
def test_estimate_interest_rate(date_str, expected_fragment):
    result = estimate_interest_rate(date_str)
    assert expected_fragment in result, f"Expected '{expected_fragment}' in '{result}'"


# ---------------------------------------------------------------------------
# is_high_rate_era
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "date_str, expected",
    [
        ("01/01/2022", True),
        ("12/31/2023", True),
        ("06/15/2021", False),
        ("03/01/2024", False),
        ("", False),
    ],
)
def test_is_high_rate_era(date_str, expected):
    assert is_high_rate_era(date_str) == expected


# ---------------------------------------------------------------------------
# is_older_than_years
# ---------------------------------------------------------------------------


def test_is_older_than_years_old_date():
    old_date = (datetime.now() - timedelta(days=25 * 365)).strftime("%m/%d/%Y")
    assert is_older_than_years(old_date, 20) is True


def test_is_older_than_years_recent_date():
    recent_date = (datetime.now() - timedelta(days=5 * 365)).strftime("%m/%d/%Y")
    assert is_older_than_years(recent_date, 20) is False


def test_is_older_than_years_empty():
    assert is_older_than_years("", 20) is False


# ---------------------------------------------------------------------------
# BaseScraper.is_flipper
# ---------------------------------------------------------------------------


def test_is_flipper_two_within_12_months():
    transfers = [
        {"date": "01/01/2023"},
        {"date": "08/15/2023"},  # ~7 months apart
    ]
    assert BaseScraper.is_flipper(transfers) is True


def test_is_flipper_two_beyond_12_months():
    transfers = [
        {"date": "01/01/2022"},
        {"date": "03/01/2023"},  # ~14 months apart
    ]
    assert BaseScraper.is_flipper(transfers) is False


def test_is_flipper_three_with_one_pair_within_12():
    transfers = [
        {"date": "01/01/2021"},
        {"date": "02/01/2022"},  # ~13 months from first
        {"date": "09/01/2022"},  # ~7 months from second  ← triggers flipper
    ]
    assert BaseScraper.is_flipper(transfers) is True


def test_is_flipper_single_transfer():
    assert BaseScraper.is_flipper([{"date": "01/01/2023"}]) is False


def test_is_flipper_empty():
    assert BaseScraper.is_flipper([]) is False


def test_is_flipper_invalid_dates():
    transfers = [{"date": "not-a-date"}, {"date": "also-bad"}]
    assert BaseScraper.is_flipper(transfers) is False


# ---------------------------------------------------------------------------
# BaseScraper.is_past_financing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "deed_type, expected",
    [
        ("Certificate of Title", True),
        ("CERTIFICATE OF TITLE", True),
        ("Satisfaction of Mortgage", True),
        ("Satisfaction Of Mortgage", True),
        ("Warranty Deed", False),
        ("Quit Claim Deed", False),
        ("", False),
    ],
)
def test_is_past_financing(deed_type, expected):
    assert BaseScraper.is_past_financing(deed_type) == expected


# ---------------------------------------------------------------------------
# BaseScraper.parse_html / safe_text
# ---------------------------------------------------------------------------


def test_parse_html_returns_soup():
    from bs4 import BeautifulSoup

    html = "<html><body><p>Hello</p></body></html>"
    soup = BaseScraper.parse_html(html)
    assert isinstance(soup, BeautifulSoup)
    assert soup.find("p").get_text() == "Hello"


def test_safe_text_none():
    assert BaseScraper.safe_text(None) == ""


def test_safe_text_element():
    soup = BaseScraper.parse_html("<span>  Hello World  </span>")
    el = soup.find("span")
    assert BaseScraper.safe_text(el) == "Hello World"
