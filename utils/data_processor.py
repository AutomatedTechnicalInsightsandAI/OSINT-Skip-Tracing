"""
Data processor: merges property records with skip-traced contact info.
"""

from __future__ import annotations

import logging
from typing import List

import pandas as pd

from scrapers.base_scraper import PropertyRecord
from skip_tracing.google_dorking import GoogleDorker

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Merge property records with skip-traced email/LinkedIn data.

    Parameters
    ----------
    enable_skip_tracing:
        When True the processor will run Google Dork queries for each unique
        owner name found in the property records.  This is slow (~10-20 s per
        owner due to mandatory rate-limit pauses) so it can be disabled for
        quick runs.
    max_skip_trace_per_batch:
        Hard cap on the number of owners to skip-trace in one batch.
    """

    def __init__(
        self,
        enable_skip_tracing: bool = True,
        max_skip_trace_per_batch: int = 20,
    ):
        self.enable_skip_tracing = enable_skip_tracing
        self.max_skip_trace_per_batch = max_skip_trace_per_batch
        self._dorker = GoogleDorker()

    def process(self, records: List[PropertyRecord]) -> pd.DataFrame:
        """
        Return a DataFrame with all required CSV columns.

        If *enable_skip_tracing* is True, the ``Scraped Emails`` column is
        populated via Google Dorking.
        """
        if not records:
            return pd.DataFrame(columns=self._column_order())

        df = pd.DataFrame([r.to_dict() for r in records])

        if self.enable_skip_tracing:
            df = self._attach_emails(df)

        # Ensure column order matches the required CSV spec
        for col in self._column_order():
            if col not in df.columns:
                df[col] = ""

        return df[self._column_order() + [c for c in df.columns if c not in self._column_order()]]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _attach_emails(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run skip-tracing and populate the 'Scraped Emails' column."""
        unique_owners = (
            df["Owner Name"]
            .dropna()
            .unique()
            .tolist()
        )
        unique_owners = [o for o in unique_owners if o.strip()][
            : self.max_skip_trace_per_batch
        ]

        email_map: dict[str, str] = {}
        for owner in unique_owners:
            logger.info("Skip-tracing: %s", owner)
            try:
                result = self._dorker.search(owner)
                emails = result.get("emails", [])
                email_map[owner] = "; ".join(emails) if emails else ""
            except Exception as exc:
                logger.warning("Skip-trace failed for '%s': %s", owner, exc)
                email_map[owner] = ""

        df["Scraped Emails"] = df["Owner Name"].map(email_map).fillna("")
        return df

    @staticmethod
    def _column_order() -> list[str]:
        """Required CSV column order per the problem specification."""
        return [
            "Owner Name",
            "Property Address",
            "Mailing Address",
            "Last Sale Date",
            "Estimated Interest Rate",
            "Scraped Emails",
        ]
