"""
Data processor: merges property records with skip-traced contact info.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List

import pandas as pd

from scrapers.base_scraper import LeadType, PropertyRecord
from skip_tracing.google_dorking import GoogleDorker

logger = logging.getLogger(__name__)
CASHOUT_REFI_MAX_LTV = 0.70


def classify_lead(row: dict) -> str:
    owner = str(row.get("Owner Name", "")).upper()
    prop_addr = str(row.get("Property Address", "")).upper().strip()
    mail_addr = str(row.get("Mailing Address", "")).upper().strip()
    is_heloc = str(row.get("Is HELOC", "")).lower() in ("true", "1", "yes")
    balloon_bal_raw = str(row.get("Balloon Balance", "")).strip()
    maturity = str(row.get("Maturity Date", "")).strip()
    sales_strat = str(row.get("Sales Strategy", "")).strip()

    if sales_strat and sales_strat != "Mortgage Mod – Review for Refi":
        return sales_strat

    trust_tokens = ["TRUST", "TTEE", "TRUSTEE", "LAND TRUST", "REVOCABLE", "LIVING TRUST"]
    is_trust = any(t in owner for t in trust_tokens)
    is_absentee = bool(prop_addr and mail_addr and prop_addr != mail_addr)

    if is_heloc:
        return "HELOC – Review Credit Limit & Terms"
    try:
        if balloon_bal_raw and float(balloon_bal_raw.replace(",", "")) > 0:
            return f"Balloon Due: {maturity}" if maturity else "Balloon – Maturity Date TBD"
    except ValueError:
        pass
    if is_trust and is_absentee:
        return "Trust DSCR Candidate – Absentee Owner"
    if is_trust:
        return "Trust – Potential Equity Refi"
    mtg_amt_at_purchase = str(row.get("Mtg Amt At Purchase", "")).replace(",", "").strip()
    sale_price = str(row.get("Sale Price", "")).strip()
    just_value = str(row.get("Just Value", "")).strip()
    modified_principal = str(row.get("Modified Principal", "")).strip()
    if mtg_amt_at_purchase == "0":
        return "Cash-Out Refi Candidate – Equity Available"
    try:
        mod_principal_float = float((modified_principal or "0").replace(",", ""))
        if mod_principal_float > 0:
            for value_str in (sale_price, just_value):
                value_float = float((value_str or "0").replace(",", ""))
                if value_float > 0 and (mod_principal_float / value_float) < CASHOUT_REFI_MAX_LTV:
                    return "Cash-Out Refi Candidate – Equity Available"
    except (ValueError, ZeroDivisionError):
        pass
    return "Mortgage Mod – Review for Refi"


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
        df["Sales Strategy"] = df.apply(classify_lead, axis=1)

        if self.enable_skip_tracing:
            df = self._attach_emails(df)

        df = self._add_derived_columns(df)

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
        rate_limited = False
        for owner in unique_owners:
            if rate_limited:
                logger.info(
                    "Skip-tracing paused for remaining owners because Google rate-limited the session"
                )
                email_map[owner] = ""
                continue
            logger.info("Skip-tracing: %s", owner)
            try:
                result = self._dorker.search(owner)
                emails = result.get("emails", [])
                email_map[owner] = "; ".join(emails) if emails else ""
                if result.get("cached"):
                    logger.info("Skip-tracing cache hit: %s", owner)
                if result.get("rate_limited"):
                    rate_limited = True
                    logger.warning(
                        "Skip-tracing hit Google rate limits; keeping partial results and stopping additional lookups"
                    )
            except Exception as exc:
                logger.warning("Skip-trace failed for '%s': %s", owner, exc)
                email_map[owner] = ""

        df["Scraped Emails"] = df["Owner Name"].map(email_map).fillna("")
        return df

    def _add_derived_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lead-scoring and Prime Coastal targeting columns."""
        df = df.copy()

        numeric_map = {
            "Sale Price": "Sale Price Num",
            "Just Value": "Just Value Num",
            "Assessed Value": "Assessed Value Num",
            "Taxable Value": "Taxable Value Num",
            "Mtg Amt At Purchase": "Mtg Amt Num",
            "Year Built": "Year Built Num",
        }
        for source_col, temp_col in numeric_map.items():
            if source_col in df.columns:
                df[temp_col] = df[source_col].apply(self._to_number)
            else:
                df[temp_col] = pd.NA

        if "Absentee Owner" not in df.columns:
            df["Absentee Owner"] = ""
        df["Absentee Owner"] = df.apply(
            lambda row: self._coalesce_bool(
                row.get("Absentee Owner"),
                self._is_absentee(
                    row.get("Mailing Address", ""),
                    row.get("Property Address", ""),
                ),
            ),
            axis=1,
        )

        sale_dates = (
            df["Last Sale Date"].apply(self._parse_date)
            if "Last Sale Date" in df.columns
            else pd.Series([pd.NaT] * len(df))
        )
        maturity_dates = (
            df["Maturity Date"].apply(self._parse_date)
            if "Maturity Date" in df.columns
            else pd.Series([pd.NaT] * len(df))
        )
        df["Sale Year"] = sale_dates.apply(
            lambda value: int(value.year) if pd.notna(value) else pd.NA
        )
        today = pd.Timestamp(datetime.now().date())
        df["Years Since Sale"] = sale_dates.apply(
            lambda value: round((today - value).days / 365.25, 1)
            if pd.notna(value)
            else pd.NA
        )
        df["Months To Maturity"] = maturity_dates.apply(
            lambda value: round((value - today).days / 30.44, 1)
            if pd.notna(value)
            else pd.NA
        )

        just = df["Just Value Num"]
        mtg = df["Mtg Amt Num"].fillna(0)
        sale_price = df["Sale Price Num"]
        assessed = df["Assessed Value Num"]
        year_built = df["Year Built Num"]
        vi = (
            df["VI"].fillna("").astype(str).str.strip().str.upper()
            if "VI" in df.columns
            else pd.Series([""] * len(df))
        )

        df["Estimated Current LTV"] = (
            mtg / just.where(just > 0)
        ).round(4)
        df["Est Equity Pct"] = (
            (just - mtg) / just.where(just > 0)
        ).round(4)
        df["Equity"] = (just - mtg).where(just.notna(), pd.NA).round(0)
        df["Mortgage Balance"] = mtg.round(0)

        recent_sale = sale_dates.apply(
            lambda value: pd.notna(value) and value >= pd.Timestamp("2022-01-01")
        )
        recent_purchase = sale_dates.apply(
            lambda value: pd.notna(value) and value >= today - pd.Timedelta(days=183)
        )
        peak_rate_purchase = sale_dates.apply(
            lambda value: pd.notna(value)
            and pd.Timestamp("2023-07-01") <= value <= pd.Timestamp("2024-09-30")
        )
        dscr_window = sale_dates.apply(
            lambda value: pd.notna(value)
            and pd.Timestamp("2022-01-01") <= value <= pd.Timestamp("2023-12-31")
        )
        old_hold = sale_dates.apply(
            lambda value: pd.notna(value) and value <= today - pd.Timedelta(days=365 * 20)
        )

        confirmed_zero_mortgage = mtg.notna() & mtg.eq(0)
        transfer_velocity_flag = (
            ((vi == "V") & sale_price.notna() & just.notna() & (sale_price < (just * 0.8)))
            | (year_built.notna() & (year_built < 1980) & just.notna() & assessed.notna() & (just > assessed * 1.2))
        )
        dscr_flag = mtg.gt(0) & dscr_window
        equity_rich_flag = mtg.fillna(0).le(0) & old_hold
        cashout_refi_flag = (
            peak_rate_purchase
            & sale_price.fillna(0).ge(250000)
            & confirmed_zero_mortgage
        )
        maturing_loan_flag = maturity_dates.apply(
            lambda value: pd.notna(value)
            and today <= value <= today + pd.Timedelta(days=365)
        )

        df["Transfer Velocity Candidate"] = transfer_velocity_flag
        df["DSCR Prospect"] = dscr_flag
        df["Equity Rich Candidate"] = equity_rich_flag
        df["Recent Sale Candidate"] = recent_sale
        df["Recent Purchase Candidate"] = recent_purchase
        df["Peak Rate Purchase Candidate"] = peak_rate_purchase
        df["Cash-Out Refi Candidate"] = cashout_refi_flag
        df["Maturing Loan Candidate"] = maturing_loan_flag

        df["Lead Strategy"] = df.apply(self._pick_lead_strategy, axis=1)
        df["Lead Score"] = df.apply(self._score_lead, axis=1)
        df["Lead Source"] = df.get("Lead Source", pd.Series(["OSINT Scraper"] * len(df))).fillna("OSINT Scraper")

        drop_cols = list(numeric_map.values())
        return df.drop(columns=[col for col in drop_cols if col in df.columns])

    @staticmethod
    def _pick_lead_strategy(row: pd.Series) -> str:
        if bool(row.get("Cash-Out Refi Candidate", False)):
            return LeadType.CASHOUT_REFI.value
        if row.get("Lead Type", "") == LeadType.BALLOON_PROSPECTS.value:
            return row.get("Lead Type", "")
        if bool(row.get("Maturing Loan Candidate", False)):
            return LeadType.BALLOON_PROSPECTS.value
        if any(
            bool(row.get(flag, False))
            for flag in (
                "DSCR Prospect",
                "Equity Rich Candidate",
                "Transfer Velocity Candidate",
            )
        ):
            return LeadType.BALLOON_PROSPECTS.value
        return row.get("Lead Type", "")

    @staticmethod
    def _score_lead(row: pd.Series) -> int:
        score = 25
        if bool(row.get("Absentee Owner", False)):
            score += 15
        if row.get("Lead Type", "") == LeadType.BALLOON_PROSPECTS.value:
            score += 10
        if bool(row.get("Peak Rate Purchase Candidate", False)):
            score += 10
        if bool(row.get("Cash-Out Refi Candidate", False)):
            score += 30
        if bool(row.get("Maturing Loan Candidate", False)):
            score += 25
        if bool(row.get("Transfer Velocity Candidate", False)):
            score += 20
        if bool(row.get("DSCR Prospect", False)):
            score += 25
        if bool(row.get("Equity Rich Candidate", False)):
            score += 25

        equity_pct = row.get("Est Equity Pct")
        if pd.notna(equity_pct):
            score += min(int(float(equity_pct) * 20), 15)

        just_value = DataProcessor._to_number(row.get("Just Value", ""))
        if pd.notna(just_value) and just_value >= 500000:
            score += 5

        sale_price = DataProcessor._to_number(row.get("Sale Price", ""))
        if pd.notna(sale_price) and sale_price >= 500000:
            score += 5

        return max(0, min(score, 100))

    @staticmethod
    def _parse_date(value) -> pd.Timestamp:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return pd.NaT
        text = str(value).strip()
        if not text:
            return pd.NaT
        parsed = pd.to_datetime(text, errors="coerce")
        return parsed if pd.notna(parsed) else pd.NaT

    @staticmethod
    def _to_number(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return pd.NA
        text = str(value).strip()
        if not text:
            return pd.NA
        cleaned = re.sub(r"[^\d.\-]", "", text)
        if not cleaned:
            return pd.NA
        try:
            return float(cleaned)
        except ValueError:
            return pd.NA

    @staticmethod
    def _normalize_address(value: str) -> str:
        return " ".join((value or "").upper().replace(",", " ").split())

    @classmethod
    def _is_absentee(cls, mailing_address: str, property_address: str) -> bool:
        mailing = cls._normalize_address(mailing_address)
        situs = cls._normalize_address(property_address)
        if not mailing or not situs:
            return False
        return mailing != situs

    @staticmethod
    def _coalesce_bool(existing, derived: bool) -> bool:
        if isinstance(existing, bool):
            return existing
        if existing is None or (isinstance(existing, float) and pd.isna(existing)):
            return derived
        text = str(existing).strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
        return derived

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
            "County",
            "Lead Type",
            "Lead Strategy",
            "Lead Score",
            "Property Type",
            "Current Exemptions",
            "Parcel ID",
            "Sale Price",
            "Just Value",
            "Assessed Value",
            "Taxable Value",
            "Instrument Number",
            "Mtg Amt At Purchase",
            "Mtg Amt Source",
            "Lender Name",
            "Maturity Date",
            "Months To Maturity",
            "Mortgage Balance",
            "Equity",
            "Est Equity Pct",
            "Estimated Current LTV",
            "Year Built",
            "VI",
            "Absentee Owner",
            "Recent Purchase Candidate",
            "Peak Rate Purchase Candidate",
            "Cash-Out Refi Candidate",
            "Maturing Loan Candidate",
            "Transfer Velocity Candidate",
            "DSCR Prospect",
            "Equity Rich Candidate",
            "PDF Extraction Method",
            "View Image URL",
            "Lead Source",
        ]
