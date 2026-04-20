"""
PDF text extraction helpers with OCR fallback for scanned clerk records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
from typing import Union

from dateutil import parser as _dp
from PIL import Image


PdfSource = Union[bytes, bytearray, str, Path]


@dataclass
class PdfTextExtraction:
    """Text extracted from a PDF plus the method used."""

    text: str = ""
    method: str = "none"
    page_count: int = 0


@dataclass
class MortgageDocumentInfo:
    """Structured terms pulled from a mortgage document PDF."""

    instrument_number: str = ""
    borrower_name: str = ""
    borrower_address: str = ""
    lender_name: str = ""
    lender_address: str = ""
    trust_name: str = ""
    credit_limit: str = ""
    interest_rate: str = ""
    maturity_date: str = ""
    balloon_balance: str = ""
    doc_stamp_mortgage: str = ""
    intangible_tax: str = ""
    extraction_method: str = "none"
    extracted_text: str = ""


@dataclass
class ModAgreementInfo:
    """Structured terms pulled from a mortgage modification agreement PDF."""

    borrower_name: str = ""
    borrower_address: str = ""
    lender_address: str = ""
    trust_name: str = ""
    property_address: str = ""
    instrument_number: str = ""
    modified_principal: str = ""
    interest_rate: str = ""
    rate_type: str = ""
    maturity_date: str = ""
    is_heloc: bool = False
    credit_limit: str = ""
    balloon_balance: float = 0.0
    has_balloon_signal: bool = False
    trust_keywords_found: list[str] = field(default_factory=list)
    extraction_method: str = "none"
    extracted_text: str = ""


def extract_pdf_text(
    pdf_source: PdfSource,
    *,
    max_pages: int | None = 5,
    force_ocr: bool = False,
) -> PdfTextExtraction:
    """
    Extract text from a PDF using the native text layer first, then OCR.

    Sarasota clerk record PDFs are frequently image-only scans, so OCR is the
    normal fallback path after a light text-layer check.
    """
    pdf_bytes = _load_pdf_bytes(pdf_source)
    page_count = _count_pdf_pages(pdf_bytes)

    if not force_ocr:
        text = _extract_text_with_pypdf(pdf_bytes, max_pages=max_pages)
        if _looks_like_useful_text(text):
            return PdfTextExtraction(text=text, method="text", page_count=page_count)

    text = _extract_text_with_ocr(pdf_bytes, max_pages=max_pages)
    if text.strip():
        return PdfTextExtraction(text=text, method="ocr", page_count=page_count)

    return PdfTextExtraction(text="", method="none", page_count=page_count)


def extract_mortgage_document_info(
    pdf_source: PdfSource,
    *,
    max_pages: int | None = 5,
    force_ocr: bool = False,
) -> MortgageDocumentInfo:
    """Extract and parse key mortgage fields from a PDF."""
    extraction = extract_pdf_text(
        pdf_source,
        max_pages=max_pages,
        force_ocr=force_ocr,
    )
    info = parse_mortgage_document_info(extraction.text)
    info.extraction_method = extraction.method
    info.extracted_text = extraction.text
    return info


def is_balloon_mortgage_first_page(pdf_bytes: bytes) -> bool:
    """
    Return True if page 1 of the PDF contains a balloon mortgage signal.
    Only reads the first page for speed — call this before full extraction.
    """
    if not pdf_bytes:
        return False

    try:
        text = _extract_text_with_pypdf(pdf_bytes, max_pages=1)
    except Exception:
        text = ""

    if not _looks_like_useful_text(text):
        try:
            text = _extract_text_with_ocr(pdf_bytes, max_pages=1)
        except Exception:
            text = ""

    upper = " ".join(text.upper().split())
    balloon_signals = [
        "BALLOON MORTGAGE",
        "BALLOON PAYMENT",
        "PRINCIPAL BALANCE DUE UPON MATURITY",
        "BALANCE DUE UPON MATURITY",
        "FINAL PRINCIPAL PAYMENT",
        "ENTIRE PRINCIPAL BALANCE",
        "ENTIRE UNPAID PRINCIPAL BALANCE",
    ]
    return any(signal in upper for signal in balloon_signals)


def extract_mod_agreement_info(
    pdf_source: PdfSource,
    *,
    max_pages: int | None = None,
) -> ModAgreementInfo:
    """Extract and parse mortgage modification agreement terms from a PDF."""
    extraction = extract_pdf_text(
        pdf_source,
        max_pages=max_pages,
        force_ocr=True,
    )
    text = extraction.text or ""
    flattened = _flatten_text(text)
    upper = " ".join(flattened.upper().split())

    mortgage_info = parse_mortgage_document_info(text)
    first_two_pages = extract_pdf_text(
        pdf_source,
        max_pages=2,
        force_ocr=False,
    )
    first_two_upper = " ".join((first_two_pages.text or "").upper().split())

    modified_principal = _normalize_money(
        _search_first(
            [
                r"NEW\s+PRINCIPAL\s+BALANCE[^\$\d]{0,30}\$?\s*([\d,]+(?:\.\d{1,2})?)",
                r"MODIFIED\s+PRINCIPAL\s+BALANCE[^\$\d]{0,30}\$?\s*([\d,]+(?:\.\d{1,2})?)",
                r"UNPAID\s+PRINCIPAL\s+BALANCE[^\$\d]{0,30}\$?\s*([\d,]+(?:\.\d{1,2})?)",
                r"AMENDED\s+(?:LOAN\s+)?AMOUNT[^\$\d]{0,30}\$?\s*([\d,]+(?:\.\d{1,2})?)",
                r"PRINCIPAL\s+BALANCE\s+OF[^\$\d]{0,20}\$?\s*([\d,]+(?:\.\d{1,2})?)",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    interest_rate = _normalize_percent(
        _search_first(
            [
                r"(?:annual\s+)?interest\s+rate\s*(?:of|is)?\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                r"interest\s+at\s+the\s+rate\s+of\s+([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                r"fixed\s+rate\s+(?:of|at)\s+([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                r"note\s+shall\s+bear\s+interest\s+at\s+([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    rate_type = ""
    if "FIXED RATE" in upper or "FIXED-RATE" in upper:
        rate_type = "Fixed"
    elif any(token in upper for token in ("ADJUSTABLE", " ARM ", "VARIABLE RATE")):
        rate_type = "Adjustable"

    heloc_tokens = ("LINE OF CREDIT", "REVOLVING", "HELOC", "HOME EQUITY LINE")
    is_heloc = any(token in first_two_upper for token in heloc_tokens)

    credit_limit = _normalize_money(
        _search_first(
            [
                r"Credit\s+Limit\s+is\s*\$\s*([0-9][0-9\s,\.]*)",
                r"MAXIMUM\s+CREDIT\s+LIMIT[^\$\d]{0,20}\$?\s*([0-9][0-9\s,\.]*)",
                r"LINE\s+OF\s+CREDIT[^\$\d]{0,30}\$?\s*([0-9][0-9\s,\.]*)",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    property_address = _clean_phrase(
        _search_first(
            [
                r"Property\s+Address[:\s]+(.+?)(?:\n|Borrower|Lender|Maturity|$)",
                r"Property\s+Address\s+is\s+(.+?)(?:\n|Borrower|Lender|Maturity|$)",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    balloon_patterns = [
        r"BALANCE\s+DUE\s+UPON\s+MATURITY\s+IS\s+\$([\d,]+(?:\.\d{1,2})?)",
        r"PRINCIPAL\s+BALANCE\s+DUE\s+UPON\s+MATURITY\s+IS[^$\d]{0,40}\$?\s*([\d,]+(?:\.\d{1,2})?)",
        r"FINAL\s+PRINCIPAL\s+PAYMENT[^$\d]{0,60}\$?\s*([\d,]+(?:\.\d{1,2})?)",
    ]
    balloon_balance = 0.0
    for pattern in balloon_patterns:
        match = re.search(pattern, upper)
        if not match:
            continue
        try:
            balloon_balance = float(match.group(1).replace(",", ""))
            break
        except ValueError:
            continue
    has_balloon_signal = any(
        token in upper
        for token in (
            "BALLOON",
            "BALLOON PAYMENT",
            "BALLOON MORTGAGE",
            "BALANCE DUE UPON MATURITY",
            "FINAL PRINCIPAL PAYMENT",
            "ENTIRE PRINCIPAL BALANCE",
        )
    )

    trust_tokens = ["TRUST", "TTEE", "TRUSTEE", "LAND TRUST", "REVOCABLE", "LIVING TRUST"]
    trust_keywords_found = [token for token in trust_tokens if token in upper]

    info = ModAgreementInfo(
        borrower_name=mortgage_info.borrower_name,
        borrower_address=mortgage_info.borrower_address,
        lender_address=mortgage_info.lender_address,
        trust_name=mortgage_info.trust_name,
        property_address=property_address,
        instrument_number=mortgage_info.instrument_number,
        modified_principal=modified_principal,
        interest_rate=interest_rate or mortgage_info.interest_rate,
        rate_type=rate_type,
        maturity_date=mortgage_info.maturity_date,
        is_heloc=is_heloc,
        credit_limit=credit_limit or mortgage_info.credit_limit,
        balloon_balance=balloon_balance,
        has_balloon_signal=has_balloon_signal,
        trust_keywords_found=trust_keywords_found,
        extraction_method=extraction.method,
        extracted_text=text,
    )
    return info


def parse_mortgage_document_info(text: str) -> MortgageDocumentInfo:
    """Parse key mortgage fields from extracted document text."""
    info = MortgageDocumentInfo()
    if not text:
        return info

    flattened = _flatten_text(text)

    info.instrument_number = _search_first(
        [
            r"INSTRUMENT\s*#\s*([0-9]{8,})",
            r"RECORDED\s+IN\s+OFFICIAL\s+RECORDS\s+([0-9]{8,})",
        ],
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    info.borrower_name = _clean_phrase(
        _search_first(
            [
                r"Borrower.{0,20}name\s+and\s+address\s+is:\s*(.*?),\s*(?:a\s+married|a\s+single|whose\s+post\s+office)",
                r"[\"']?Borrower.{0,25}?\bis\b\s+(.+?)\s+the party or parties who have signed this Security Instrument",
                r"[\"']?Borrower.{0,25}?\bis\b\s+(.+?)\s+Borrower is the Mortgagor",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    info.lender_name = _clean_phrase(
        _search_first(
            [
                r"['\"]?Lender['\"]?\s+is\s+(.+?)\.\s+Lender\s+is",
                r"After\s+Recording\s+Return\s+To:\s*(.+?)\s+Document\s+Imaging",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    address_matches = [
        _clean_phrase(match)
        for match in re.findall(
            r"whose\s+(?:post\s+office\s+)?address\s+is\s+(.+?)(?=,\s*(?:and\s+|['\"]?\(?Lender|$)|[.;\n])",
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if _clean_phrase(match)
    ]
    if address_matches:
        info.borrower_address = address_matches[0]
    if len(address_matches) > 1:
        info.lender_address = address_matches[1]

    info.trust_name = _clean_phrase(
        _search_first(
            [
                r"Trustees?\s+of\s+(?:the\s+)?(.+?\bTrust(?:\s+dated\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})?)\s*\(\s*['\"]?Lender['\"]?\s*\)",
                r"Trustees?\s+of\s+(?:the\s+)?(.+?\bTrust(?:\s+dated\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})?)",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    info.credit_limit = _normalize_money(
        _search_first(
            [r"Credit\s+Limit\s+is\s*\$\s*([0-9][0-9\s,\.]*)"],
            flattened,
            flags=re.IGNORECASE,
        )
    )

    info.interest_rate = _normalize_percent(
        _search_first(
            [
                r"(?:annual\s+)?interest\s+rate\s*(?:of|is)?\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                r"interest\s+at\s+the\s+rate\s+of\s+([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                r"fixed\s+rate\s+(?:of|at)\s+([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
                r"note\s+shall\s+bear\s+interest\s+at\s+([0-9]{1,2}(?:\.[0-9]+)?)\s*%",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    info.maturity_date = _normalize_date_phrase(
        _search_first(
            [
                r"due\s+by\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
                r"Maturity\s+Date.{0,500}?((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}[,\.]?\s+\d{4})",
                r"Maturity\s+Date.*?Instrument,\s+is\s+due\s+on\s+(.+?)\s+(?:as\s|Borrower|The\s+Note|$)",
                r"Maturity\s+Date.*?due\s+on\s+(.+?)\s+(?:as\s|Borrower|The\s+Note|$)",
                r"due\s+by\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}[,\.]?\s+\d{4})\s*\(?['\"]?Maturity\s+Date",
            ],
            flattened,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )

    info.balloon_balance = _normalize_money(
        _search_first(
            [r"BALANCE\s+DUE\s+UPON\s+MATURITY\s+IS\s+\$([\d,]+(?:\.\d{1,2})?)"],
            flattened,
            flags=re.IGNORECASE,
        )
    )

    info.doc_stamp_mortgage = _normalize_money(
        _search_first(
            [r"Doc\s*stamp-?Mort:\s*\$\s*([0-9][0-9\s,\.]*)"],
            flattened,
            flags=re.IGNORECASE,
        )
    )

    info.intangible_tax = _normalize_money(
        _search_first(
            [r"Intang\.?\s*Tax:\s*\$\s*([0-9][0-9\s,\.]*)"],
            flattened,
            flags=re.IGNORECASE,
        )
    )

    return info


def _load_pdf_bytes(pdf_source: PdfSource) -> bytes:
    if isinstance(pdf_source, (bytes, bytearray)):
        return bytes(pdf_source)
    return Path(pdf_source).read_bytes()


def _count_pdf_pages(pdf_bytes: bytes) -> int:
    from pypdf import PdfReader

    with BytesIO(pdf_bytes) as handle:
        return len(PdfReader(handle).pages)


def _extract_text_with_pypdf(pdf_bytes: bytes, *, max_pages: int | None = 5) -> str:
    from pypdf import PdfReader

    chunks: list[str] = []
    with BytesIO(pdf_bytes) as handle:
        reader = PdfReader(handle)
        pages = reader.pages[:max_pages] if max_pages else reader.pages
        for page in pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                chunks.append(page_text)
    return "\n".join(chunks).strip()


def _extract_text_with_ocr(pdf_bytes: bytes, *, max_pages: int | None = 5) -> str:
    import fitz

    ocr_engine = _get_ocr_engine()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_text: list[str] = []
    try:
        limit = min(len(doc), max_pages) if max_pages else len(doc)
        for index in range(limit):
            page = doc[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            with BytesIO() as buffer:
                image.save(buffer, format="PNG")
                result, _ = ocr_engine(
                    buffer.getvalue(),
                    use_det=True,
                    use_cls=True,
                    use_rec=True,
                )

            lines: list[str] = []
            if result:
                for item in result:
                    if len(item) < 2:
                        continue
                    text_value = item[1]
                    if isinstance(text_value, (tuple, list)):
                        text_value = text_value[0]
                    cleaned = str(text_value).strip()
                    if cleaned:
                        lines.append(cleaned)
            if lines:
                page_text.append("\n".join(lines))
    finally:
        doc.close()
    return "\n\n".join(page_text).strip()


@lru_cache(maxsize=1)
def _get_ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _looks_like_useful_text(text: str) -> bool:
    if not text:
        return False
    compact = re.sub(r"\s+", " ", text).strip()
    return len(compact) >= 20 and any(char.isalpha() for char in compact)


def _flatten_text(text: str) -> str:
    flattened = re.sub(r"[ \t]+", " ", text)
    flattened = re.sub(r"\n+", "\n", flattened)
    return flattened


def _search_first(patterns: list[str], text: str, *, flags: int = 0) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip()
    return ""


def _clean_phrase(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value).strip(" .,:;")
    return value


def _normalize_money(value: str) -> str:
    if not value:
        return ""
    compact = value.replace(" ", "").replace(",", "")
    match = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)", compact)
    return match.group(1) if match else ""


def _normalize_date_phrase(value: str) -> str:
    if not value:
        return ""
    cleaned = _clean_phrase(value).replace(" .", ".")
    month_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2}[,\.]?\s+\d{4}",
        cleaned,
        re.IGNORECASE,
    )
    if month_match:
        return month_match.group(0).replace(".", ",")
    return cleaned


def _normalize_percent(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"([0-9]{1,2}(?:\.[0-9]+)?)", value)
    if not match:
        return ""
    return f"{match.group(1)}%"


def _parse_date_flexible(date_str: str) -> datetime | None:
    """Parse OCR date text with fuzzy matching and return a datetime when possible."""
    if not date_str:
        return None
    try:
        return _dp.parse(date_str, fuzzy=True)
    except (TypeError, ValueError, OverflowError):
        return None


def estimate_principal_from_doc_stamp(doc_stamp_str: str) -> float:
    """Estimate principal from Florida doc stamp tax using (doc_stamp / 0.35) * 100."""
    try:
        amount = float((doc_stamp_str or "").replace(",", "").replace("$", "").strip())
        if amount <= 0:
            return 0.0
        return round((amount / 0.35) * 100, 2)
    except ValueError:
        return 0.0
