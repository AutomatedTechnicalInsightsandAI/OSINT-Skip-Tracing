"""
Tests for OCR-backed PDF extraction and mortgage term parsing.
"""

from __future__ import annotations

from utils.pdf_reader import (
    MortgageDocumentInfo,
    _parse_date_flexible,
    estimate_principal_from_doc_stamp,
    extract_mortgage_document_info,
    extract_pdf_text,
    is_balloon_mortgage_first_page,
    parse_mortgage_document_info,
)


SAMPLE_OCR_TEXT = """
RECORDED IN OFFICIAL RECORDS
2026047868
INSTRUMENT #
PG(S)
411312026 10:15 AM
KAREN E. RUSHING
BANK OF AMERICA, N.A.
Doc stamp-Mort: $875.00
Intang. Tax: $500.00

'Lender' is Bank of America, N. A. Lender is a National Banking Association organized and existing under the
laws of the United States of America. Lender is the Mortgagee under this Security Instrument.

The Note shall bear interest at 8.75% per annum.

"Credit Limit" means the maximum aggregate amount of principal that may be secured by this Security
Instrument at any one time. The Credit Limit is $ 2 5 0 , 0 0 0 . 0 0

(H)
"Maturity Date" is the date on which the entire Account Balance under the Agreement is due. The entire
defined in the Agreement and this Security
the Account,
Balance on
Account
Instrument, is due on
. as c
April 1. 2056
"""


def test_parse_mortgage_document_info_extracts_core_fields():
    info = parse_mortgage_document_info(SAMPLE_OCR_TEXT)

    assert isinstance(info, MortgageDocumentInfo)
    assert info.instrument_number == "2026047868"
    assert info.borrower_name == ""
    assert info.lender_name == "Bank of America, N. A"
    assert info.credit_limit == "250000.00"
    assert info.interest_rate == "8.75%"
    assert info.maturity_date == "April 1, 2056"
    assert info.doc_stamp_mortgage == "875.00"
    assert info.intangible_tax == "500.00"


def test_parse_mortgage_document_info_extracts_borrower_name():
    info = parse_mortgage_document_info(
        """
        'Borrower' is SUNCOAST OFFICE PARK LLC, a Florida limited liability company,
        the party or parties who have signed this Security Instrument.
        'Lender' is Example Bank, N.A.
        """
    )

    assert info.borrower_name == "SUNCOAST OFFICE PARK LLC, a Florida limited liability company"


def test_extract_pdf_text_prefers_native_text(monkeypatch):
    monkeypatch.setattr("utils.pdf_reader._count_pdf_pages", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_pypdf",
        lambda *_args, **_kwargs: "Text layer found in pdf",
    )
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_ocr",
        lambda *_args, **_kwargs: "OCR should not be used",
    )

    extraction = extract_pdf_text(b"%PDF-sample")

    assert extraction.method == "text"
    assert extraction.text == "Text layer found in pdf"
    assert extraction.page_count == 1


def test_extract_pdf_text_falls_back_to_ocr(monkeypatch):
    monkeypatch.setattr("utils.pdf_reader._count_pdf_pages", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_pypdf",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_ocr",
        lambda *_args, **_kwargs: SAMPLE_OCR_TEXT,
    )

    extraction = extract_pdf_text(b"%PDF-scan")

    assert extraction.method == "ocr"
    assert "2026047868" in extraction.text
    assert extraction.page_count == 2


def test_extract_mortgage_document_info_uses_pdf_text_path(monkeypatch):
    monkeypatch.setattr(
        "utils.pdf_reader.extract_pdf_text",
        lambda *_args, **_kwargs: type(
            "Extraction",
            (),
            {"text": SAMPLE_OCR_TEXT, "method": "ocr", "page_count": 7},
        )(),
    )

    info = extract_mortgage_document_info(b"%PDF-scan")

    assert info.extraction_method == "ocr"
    assert info.instrument_number == "2026047868"
    assert info.credit_limit == "250000.00"


def test_parse_mortgage_document_info_extracts_reverse_maturity_date_phrase():
    info = parse_mortgage_document_info(
        """
        ... to be due by November 10, 2021 ("Maturity Date") and payable in full.
        """
    )

    assert info.maturity_date == "November 10, 2021"


def test_parse_mortgage_document_info_extracts_due_by_without_maturity_label():
    info = parse_mortgage_document_info(
        """
        The entire principal balance shall be due by November 10, 2026 and payable in full.
        """
    )

    assert info.maturity_date == "November 10, 2026"


def test_parse_mortgage_document_info_extracts_balloon_balance_and_borrower_name_anchor():
    info = parse_mortgage_document_info(
        """
        Borrower's name and address is:
        SUNCOAST OFFICE PARTNERS LLC, a single member limited liability company
        THIS IS A BALLOON MORTGAGE. THE PRINCIPAL BALANCE DUE UPON MATURITY IS $280,000.00.
        """
    )

    assert info.borrower_name == "SUNCOAST OFFICE PARTNERS LLC"
    assert info.balloon_balance == "280000.00"


def test_parse_date_flexible_accepts_ocr_style_date():
    parsed = _parse_date_flexible("to be due by 10th day of November, 2026 (Maturity Date)")

    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 11
    assert parsed.day == 10


def test_estimate_principal_from_doc_stamp_uses_florida_formula():
    assert estimate_principal_from_doc_stamp("$980.00") == 280000.0
    assert estimate_principal_from_doc_stamp("") == 0.0


def test_is_balloon_mortgage_first_page_uses_text_layer_first(monkeypatch):
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_pypdf",
        lambda *_args, **_kwargs: "THIS IS A BALLOON MORTGAGE",
    )
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_ocr",
        lambda *_args, **_kwargs: "",
    )

    assert is_balloon_mortgage_first_page(b"%PDF") is True


def test_is_balloon_mortgage_first_page_falls_back_to_ocr(monkeypatch):
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_pypdf",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_ocr",
        lambda *_args, **_kwargs: "principal balance due upon maturity is $180,000.00",
    )

    assert is_balloon_mortgage_first_page(b"%PDF") is True


def test_is_balloon_mortgage_first_page_returns_false_for_empty_or_invalid_pdf(monkeypatch):
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_pypdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad pdf")),
    )
    monkeypatch.setattr(
        "utils.pdf_reader._extract_text_with_ocr",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("ocr failed")),
    )

    assert is_balloon_mortgage_first_page(b"") is False
    assert is_balloon_mortgage_first_page(b"%PDF-bad") is False
