"""
PDF text extraction helpers with OCR fallback for scanned clerk records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
from typing import Union

from dateutil import parser as dateutil_parser
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
    lender_name: str = ""
    credit_limit: str = ""
    interest_rate: str = ""
    maturity_date: str = ""
    doc_stamp_mortgage: str = ""
    intangible_tax: str = ""
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
                r"Borrower.{0,10}name\s+and\s+address\s+is:\s*(.*?),\s*(?:a\s+married|a\s+single|whose\s+post)",
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

    maturity_phrase = _search_first(
        [
            r"due\s+by\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
            r"Maturity\s+Date.{0,500}?((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}[,\.]?\s+\d{4})",
        ],
        flattened,
        flags=re.IGNORECASE | re.DOTALL,
    )
    parsed_maturity = _parse_date_flexible(maturity_phrase)
    if parsed_maturity:
        info.maturity_date = f"{parsed_maturity.strftime('%B')} {parsed_maturity.day}, {parsed_maturity.year}"
    else:
        info.maturity_date = _normalize_date_phrase(maturity_phrase)

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
    if not date_str:
        return None
    try:
        return dateutil_parser.parse(date_str, fuzzy=True)
    except Exception:
        return None


def estimate_principal_from_doc_stamp(doc_stamp_str: str) -> float:
    """Florida doc stamp formula: (doc_stamps / 0.35) * 100 = principal."""
    try:
        amount = float((doc_stamp_str or "").replace(",", "").replace("$", "").strip())
        return round((amount / 0.35) * 100, 2)
    except (ValueError, ZeroDivisionError):
        return 0.0
