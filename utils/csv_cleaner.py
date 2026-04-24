"""
CSV Cleaner for raw owner/mailing address exports.

Handles messy county data exports:
- Auto-detects name and address columns (fuzzy matching)
- Normalizes LLC / individual name formatting
- Cleans and standardizes mailing addresses
- Outputs a clean CSV with two canonical columns:
    "Owner Name"  |  "Mailing Address"
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from rapidfuzz import process as fuzz_process  # pip install rapidfuzz

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name fuzzy-detection candidates
# ---------------------------------------------------------------------------

_NAME_CANDIDATES = [
    "owner name", "owner", "name", "grantor", "taxpayer", "llc name",
    "owner 1", "owner1", "primary owner", "mailing name",
    "owner name first last", "certified owner name", "owner full name",
    "owner name last first",
]

_ADDRESS_CANDIDATES = [
    "mailing address", "mail address", "mailing addr", "address", "addr",
    "mail addr", "owner address", "correspondence address", "contact address",
    "owner add 1", "owner add", "owner add1",
    "mail add 1", "mail add", "mailing add 1",
    "property address", "situs address",
]

# ---------------------------------------------------------------------------
# LLC suffix normalization map  (all caps → canonical)
# ---------------------------------------------------------------------------
_LLC_SUFFIXES = re.compile(
    r"\b(LLC|L\.L\.C\.?|L\.C\.?|LTD|INC\.?|CORP\.?|CO\.?)\b",
    re.IGNORECASE,
)

# Noise tokens often appended to owner names from county exports
_NOISE_TOKENS = re.compile(
    r"\s*(ETAL|ET AL|C/O|%|ATTN:?|&amp;)\s*",
    re.IGNORECASE,
)


class CSVCleaner:
    """
    Load a raw CSV, detect and clean name + address columns.

    Parameters
    ----------
    name_col:
        Override the auto-detected owner name column.
    address_col:
        Override the auto-detected mailing address column.
    fuzzy_threshold:
        Minimum score (0-100) for fuzzy column detection. Default 75.
    """

    def __init__(
        self,
        name_col: Optional[str] = None,
        address_col: Optional[str] = None,
        fuzzy_threshold: int = 75,
    ):
        self.name_col = name_col
        self.address_col = address_col
        self.fuzzy_threshold = fuzzy_threshold

    def load_and_clean(self, filepath: str | Path) -> pd.DataFrame:
        """
        Load *filepath* (CSV or Excel), clean it, and return a DataFrame with:

            "Owner Name"  |  "Mailing Address"

        plus any other original columns preserved.
        """
        path = Path(filepath)
        if path.suffix.lower() in {".xlsx", ".xls"}:
            raw = pd.read_excel(path, dtype=str)
        else:
            raw = pd.read_csv(path, dtype=str, encoding_errors="replace")

        raw.columns = [str(c).strip() for c in raw.columns]
        raw = raw.dropna(how="all").reset_index(drop=True)

        name_col = self.name_col or self._detect_column(raw.columns.tolist(), _NAME_CANDIDATES, "name")
        addr_col = self.address_col or self._detect_column(raw.columns.tolist(), _ADDRESS_CANDIDATES, "address")

        if not name_col:
            raise ValueError(
                "Could not auto-detect an owner-name column. "
                "Pass name_col='YourColumnName' explicitly."
            )
        if not addr_col:
            raise ValueError(
                "Could not auto-detect a mailing-address column. "
                "Pass address_col='YourColumnName' explicitly."
            )

        logger.info("Using name column: '%s', address column: '%s'", name_col, addr_col)

        df = raw.copy()
        df["Owner Name"] = df[name_col].apply(self._clean_name)
        df["Mailing Address"] = df[addr_col].apply(self._clean_address)

        # Drop rows where both cleaned fields are empty
        empty_mask = df["Owner Name"].eq("") & df["Mailing Address"].eq("")
        dropped = empty_mask.sum()
        if dropped:
            logger.warning("Dropping %d fully-empty rows", dropped)
        df = df[~empty_mask].reset_index(drop=True)

        return df

    def save(self, df: pd.DataFrame, out_path: str | Path) -> Path:
        """Write *df* to *out_path* and return the resolved path."""
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        logger.info("Cleaned CSV written to %s (%d rows)", out, len(df))
        return out

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_column(
        self, columns: list[str], candidates: list[str], label: str
    ) -> Optional[str]:
        """Fuzzy-match *columns* against *candidates* and return best hit."""
        col_lower = {c: c.lower() for c in columns}

        # Exact match first (case-insensitive)
        for col, low in col_lower.items():
            if low in candidates:
                return col

        # Try each candidate individually against each column
        best_score = 0
        best_col = None
        for candidate in candidates:
            for col, low in col_lower.items():
                result = fuzz_process.extractOne(candidate, [low], score_cutoff=self.fuzzy_threshold)
                if result and result[1] > best_score:
                    best_score = result[1]
                    best_col = col

        if best_col:
            return best_col

        logger.warning("Could not detect %s column in: %s", label, columns)
        return None

    @staticmethod
    def _clean_name(value) -> str:
        """Normalize an owner name (individual or LLC)."""
        if pd.isna(value):
            return ""
        text = str(value).strip()

        # Remove noise tokens
        text = _NOISE_TOKENS.sub(" ", text)

        # Collapse extra whitespace
        text = " ".join(text.split())

        # Title-case individual names; leave LLC-style names in UPPER
        if _LLC_SUFFIXES.search(text):
            return text.upper()

        return text.title()

    @staticmethod
    def _clean_address(value) -> str:
        """Normalize a mailing address string."""
        if pd.isna(value):
            return ""
        text = str(value).strip()

        # Remove non-printable characters
        text = re.sub(r"[^\x20-\x7E]", " ", text)

        # Collapse extra whitespace
        text = " ".join(text.split())

        return text.upper()
