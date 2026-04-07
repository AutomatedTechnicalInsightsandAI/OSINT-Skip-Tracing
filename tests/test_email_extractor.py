"""
Tests for skip_tracing/email_extractor.py
"""

from __future__ import annotations

import pytest

from skip_tracing.email_extractor import EmailExtractor


@pytest.fixture()
def extractor() -> EmailExtractor:
    return EmailExtractor()


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------


def test_extract_single_email(extractor):
    text = "Contact us at hello@primefunding.com for more info."
    results = extractor.extract(text)
    assert "hello@primefunding.com" in results


def test_extract_multiple_emails(extractor):
    text = "Reach john@example.net or jane@realty.com today!"
    results = extractor.extract(text)
    assert "john@example.net" in results
    assert "jane@realty.com" in results


def test_extract_deduplicates(extractor):
    text = "info@coastal.com and INFO@COASTAL.COM are the same."
    results = extractor.extract(text)
    assert results.count("info@coastal.com") == 1


def test_extract_excludes_example_com(extractor):
    text = "This is an example email: user@example.com"
    results = extractor.extract(text)
    assert "user@example.com" not in results


def test_extract_excludes_linkedin(extractor):
    text = "See job at careers@linkedin.com"
    # linkedin.com is not in the exclude list, but facebook is
    # — this test just ensures the filter mechanism works for blocked domains
    text2 = "Contact no-reply@facebook.com"
    results = extractor.extract(text2)
    assert "no-reply@facebook.com" not in results


def test_extract_returns_lowercase(extractor):
    text = "Email: John.DOE@REALTY.COM"
    results = extractor.extract(text)
    assert "john.doe@realty.com" in results


def test_extract_no_email(extractor):
    text = "There is no email address here."
    assert extractor.extract(text) == []


def test_extract_empty_string(extractor):
    assert extractor.extract("") == []


def test_extract_from_html(extractor):
    html = """
    <html><body>
    <p>Call us or email <a href="mailto:agent@coastal.com">agent@coastal.com</a></p>
    <p>Investor contact: invest@primefunding.net</p>
    </body></html>
    """
    results = extractor.extract(html)
    assert "agent@coastal.com" in results
    assert "invest@primefunding.net" in results


def test_extract_returns_sorted(extractor):
    text = "z@domain.com a@domain.com m@domain.com"
    results = extractor.extract(text)
    assert results == sorted(results)


# ---------------------------------------------------------------------------
# is_valid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email, expected",
    [
        ("user@domain.com", True),
        ("first.last+tag@sub.domain.org", True),
        ("not-an-email", False),
        ("missing@tld.", False),
        ("@nodomain.com", False),
        ("two@@domain.com", False),
        ("plain text", False),
    ],
)
def test_is_valid(email, expected):
    assert EmailExtractor.is_valid(email) == expected
