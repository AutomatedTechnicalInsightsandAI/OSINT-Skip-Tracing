"""
End-to-end pipeline:
  1. Load and clean a raw owner/address CSV
  2. Run skip tracing (email + phone) for each unique owner
  3. Output a results CSV with columns:
       Owner Name | Mailing Address | Phones | Emails | LinkedIn

Usage
-----
  python -m skip_tracing.csv_skip_trace_pipeline \
      --input  data/raw_owners.csv \
      --output data/skip_traced.csv \
      [--name-col "Owner Name"] \
      [--address-col "Mailing Address"] \
      [--max-owners 50]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from utils.csv_cleaner import CSVCleaner
from skip_tracing.phone_scraper import PhoneScraper
from skip_tracing.google_dorking import GoogleDorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_pipeline(
    input_path: str,
    output_path: str,
    name_col: str | None = None,
    address_col: str | None = None,
    max_owners: int = 100,
) -> pd.DataFrame:
    """
    Full pipeline: clean -> skip trace -> save.

    Returns the enriched DataFrame.
    """

    # ------------------------------------------------------------------ #
    # 1. Load + Clean                                                      #
    # ------------------------------------------------------------------ #
    logger.info("Loading and cleaning: %s", input_path)
    cleaner = CSVCleaner(name_col=name_col, address_col=address_col)
    df = cleaner.load_and_clean(input_path)
    logger.info("Cleaned dataset: %d rows", len(df))

    # ------------------------------------------------------------------ #
    # 2. De-duplicate owners for skip tracing                              #
    # ------------------------------------------------------------------ #
    pairs = (
        df[["Owner Name", "Mailing Address"]]
        .drop_duplicates(subset=["Owner Name"])
        .head(max_owners)
    )
    logger.info("Unique owners to skip-trace: %d", len(pairs))

    phone_scraper = PhoneScraper()
    email_dorker = GoogleDorker()

    phone_map: dict[str, str] = {}
    email_map: dict[str, str] = {}
    linkedin_map: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # 3. Skip trace each owner                                             #
    # ------------------------------------------------------------------ #
    for i, row in enumerate(pairs.itertuples(index=False), start=1):
        name: str = row[0]       # "Owner Name"
        address: str = row[1]    # "Mailing Address"

        logger.info("[%d/%d] Skip-tracing: %s", i, len(pairs), name)

        # --- Phone ---
        phone_result = phone_scraper.lookup(name, address)
        phone_map[name] = "; ".join(phone_result["phones"])
        if phone_result["rate_limited"]:
            logger.warning("Google rate-limited on phones - partial results only")

        # --- Email + LinkedIn ---
        email_result = email_dorker.search(name)
        email_map[name] = "; ".join(email_result["emails"])
        linkedin_map[name] = "; ".join(email_result["linkedin"])
        if email_result["rate_limited"]:
            logger.warning("Google rate-limited on emails - partial results only")

    # ------------------------------------------------------------------ #
    # 4. Merge results back to the full dataframe                          #
    # ------------------------------------------------------------------ #
    df["Phones"] = df["Owner Name"].map(phone_map).fillna("")
    df["Emails"] = df["Owner Name"].map(email_map).fillna("")
    df["LinkedIn"] = df["Owner Name"].map(linkedin_map).fillna("")

    # Reorder so key columns are first
    priority_cols = ["Owner Name", "Mailing Address", "Phones", "Emails", "LinkedIn"]
    other_cols = [c for c in df.columns if c not in priority_cols]
    df = df[priority_cols + other_cols]

    # ------------------------------------------------------------------ #
    # 5. Save                                                              #
    # ------------------------------------------------------------------ #
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    logger.info("Output saved to: %s (%d rows)", out, len(df))

    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Clean a CSV of owner/address data and skip-trace for phones + emails."
    )
    parser.add_argument("--input", required=True, help="Path to raw input CSV (or .xlsx)")
    parser.add_argument("--output", required=True, help="Path for enriched output CSV")
    parser.add_argument("--name-col", default=None, help="Override owner name column name")
    parser.add_argument("--address-col", default=None, help="Override address column name")
    parser.add_argument("--max-owners", type=int, default=100,
                        help="Max unique owners to skip-trace per run (default 100)")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    run_pipeline(
        input_path=args.input,
        output_path=args.output,
        name_col=args.name_col,
        address_col=args.address_col,
        max_owners=args.max_owners,
    )
