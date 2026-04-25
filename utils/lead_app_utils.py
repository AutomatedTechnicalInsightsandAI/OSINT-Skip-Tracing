from __future__ import annotations

import logging
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from scrapers.base_scraper import LeadType
from scrapers.broward_scraper import BrowardScraper
from scrapers.miami_dade_scraper import MiamiDadeScraper
from scrapers.sarasota_scraper import SarasotaScraper
from utils.csv_exporter import CSVExporter
from utils.data_processor import DataProcessor

logger = logging.getLogger(__name__)

COUNTY_SCRAPERS = {
    "Sarasota": SarasotaScraper,
    "Miami-Dade": MiamiDadeScraper,
    "Broward": BrowardScraper,
}

LEAD_TYPE_HELP = {
    LeadType.CASHOUT_REFI: (  # ⚠️ DO NOT CHANGE
        "Sarasota purchases with **Last Sale Date from 07/01/2023 through 09/30/2024**, "
        "**sale price > $250k**, and **no matching mortgage recorded at purchase**. "
        "These are strong cash-out refinance targets."
    ),
    LeadType.BALLOON_PROSPECTS: (
        "Balloon mortgage prospects: OCR-confirmed balloon signal from Sarasota recorded mortgage "
        "PDFs. Targets maturities due in 2026 or 2027. No interest rate floor — if they have a "
        "balloon, they must refi regardless of rate. Scans up to 1,000 PDFs per run."
    ),
    LeadType.TRUST_REFI: (
        "Properties where title is held in a trust (land trust, living trust, or revocable trust) "
        "and the owner may be a refinance candidate. Identified by trust/trustee language in the "
        "owner name or deed type. These owners often have high equity and respond well to "
        "privacy-focused outreach."
    ),
    LeadType.MORTGAGE_MOD: (
        "Mortgage modification agreements recorded at the Sarasota Clerk of Court "
        "from **January 1, 2025 through today**. Each PDF is OCR-scanned to extract "
        "the borrower name, modified principal, interest rate, maturity date, and "
        "balloon/HELOC signals. These borrowers already had a modification — they "
        "are prime candidates for a full refinance."
    ),
    LeadType.DSCR: (
        "Investment properties in Sarasota County with strong DSCR (Debt Service Coverage Ratio). "
        "Pulls from the Sarasota Property Appraiser export — **no absentee or interest-rate filters** — "
        "so you see the full universe of income-property candidates. DSCR is estimated using "
        "a 0.70%/month rent factor and 75% LTV at 7.00% / 30yr. Sort by 'DSCR Ratio' descending "
        "to prioritise the strongest cash-flowing deals."
    ),
}

OUTREACH_PRIORITY_COLUMNS = [
    "Owner Name",
    "Property Address",
    "Mailing Address",
    "Last Sale Date",
    "Sale Price",
    "Instrument Number",
    "Mtg Amt At Purchase",
    "Mtg Amt Source",
    "Lender Name",
    "Sales Strategy",
    "Modified Principal",
    "Is HELOC",
    "Credit Limit",
    "Rate Type",
    "Trust Keywords",
    "Maturity Date",
    "Lead Strategy",
    "Lead Score",
    "Absentee Owner",
    "Scraped Emails",
    "County",
    "Property Type",
    "Parcel ID",
    "Notes",
]


def _lead_state_meta(lead_type: LeadType) -> dict[str, str]:
    if lead_type == LeadType.BALLOON_PROSPECTS:
        return {
            "results_key": "balloon_results_df",
            "partial_key": "balloon_partial_df",
            "saved_csv_key": "balloon_saved_csv_path",
            "label": "balloon_balance",
        }
    if lead_type == LeadType.CASHOUT_REFI:
        return {
            "results_key": "cashout_results_df",
            "partial_key": "cashout_partial_df",
            "saved_csv_key": "cashout_saved_csv_path",
            "label": "cashout_refi",
        }
    if lead_type == LeadType.TRUST_REFI:
        return {
            "results_key": "trust_results_df",
            "partial_key": "trust_partial_df",
            "saved_csv_key": "trust_saved_csv_path",
            "label": "trust_refi",
        }
    if lead_type == LeadType.MORTGAGE_MOD:
        return {
            "results_key": "mortgage_mod_results_df",
            "partial_key": "mortgage_mod_partial_df",
            "saved_csv_key": "mortgage_mod_saved_csv_path",
            "label": "mortgage_mod_refi",
        }
    if lead_type == LeadType.DSCR:
        return {
            "results_key": "dscr_results_df",
            "partial_key": "dscr_partial_df",
            "saved_csv_key": "dscr_saved_csv_path",
            "label": "dscr_investor",
        }
    safe_name = lead_type.name.lower()
    return {
        "results_key": f"{safe_name}_results_df",
        "partial_key": f"{safe_name}_partial_df",
        "saved_csv_key": f"{safe_name}_saved_csv_path",
        "label": safe_name,
    }


def get_results_so_far_df(results_key: str, partial_key: str) -> pd.DataFrame:
    """Return the best available in-memory DataFrame for incremental download."""
    results_df = st.session_state.get(results_key, pd.DataFrame())
    partial_df = st.session_state.get(partial_key, pd.DataFrame())
    if isinstance(results_df, pd.DataFrame) and not results_df.empty:
        return results_df
    if isinstance(partial_df, pd.DataFrame) and not partial_df.empty:
        return partial_df
    return pd.DataFrame()


def render_download_leads_so_far(
    *,
    results_key: str,
    partial_key: str,
    filename_prefix: str,
    widget_key: str,
) -> None:
    """Render a live CSV download control for whatever results currently exist."""
    df = get_results_so_far_df(results_key, partial_key)
    if df.empty:
        return

    lead_count = len(df.index)
    count_column, button_column = st.columns([2, 3])
    with count_column:
        st.caption(f"{lead_count} leads found so far")
    with button_column:
        st.download_button(
            label="⬇️ Download Leads So Far",
            data=CSVExporter.to_bytes(df),
            file_name=f"{filename_prefix}_partial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            type="secondary",
            width="content",
            key=widget_key,
        )


def _records_to_dataframe(records: list) -> pd.DataFrame:
    rows = []
    for record in records:
        if isinstance(record, dict):
            rows.append(record)
        elif hasattr(record, "to_dict"):
            rows.append(record.to_dict())
        elif hasattr(record, "__dict__"):
            rows.append(dict(record.__dict__))
        else:
            logger.warning("Skipping unhandled record type in partial results: %s", type(record))
    return pd.DataFrame(rows)


def run_scrapers(config: dict) -> pd.DataFrame:
    """Execute scrapers for all selected counties and return merged DataFrame."""
    counties: list[str] = config["counties"]
    lead_type: LeadType = config["lead_type"]
    max_results: int = config["max_results"]
    headless: bool = config["headless"]
    state_meta = _lead_state_meta(lead_type)
    results_key = state_meta["results_key"]
    partial_key = state_meta["partial_key"]
    saved_csv_key = state_meta["saved_csv_key"]
    label = state_meta["label"]

    if not counties:
        st.warning("Please select at least one county in the sidebar.")
        return pd.DataFrame()

    st.session_state[partial_key] = pd.DataFrame()
    all_records = []
    progress_bar = st.progress(0, text="Initializing scrapers...")
    status = st.status("Running scrapers...", expanded=True)

    for idx, county_name in enumerate(counties):
        scraper_cls = COUNTY_SCRAPERS[county_name]
        status.write(f"Scraping **{county_name}** county...")
        try:
            with scraper_cls(headless=headless) as scraper:
                records = scraper.fetch_records(lead_type, max_results=max_results)
                all_records.extend(records)
                status.write(f"{county_name}: found **{len(records)}** record(s).")
                if records:
                    county_df = _records_to_dataframe(records)
                    partial_df = st.session_state[partial_key]
                    updated_partial_df = pd.concat(
                        [partial_df, county_df],
                        ignore_index=True,
                    )
                    st.session_state[partial_key] = updated_partial_df
                    # Keep both keys updated so page-level UI can always read either
                    # "final results" or "partial results" consistently mid-run.
                    st.session_state[results_key] = updated_partial_df
                    partial_path = save_results_csv(
                        updated_partial_df,
                        lead_type,
                        label=f"{label}_partial",
                    )
                    st.session_state[saved_csv_key] = str(partial_path)
        except Exception as exc:
            status.write(f"{county_name} scraper failed: `{exc}`")
            logger.error("Scraper %s failed: %s", county_name, traceback.format_exc())

        progress_bar.progress(
            (idx + 1) / len(counties),
            text=f"Processed {idx + 1}/{len(counties)} counties",
        )

    status.update(label="Scraping complete", state="complete")
    progress_bar.empty()

    if not all_records:
        st.warning(
            "No records returned. This can happen if the county portal "
            "structure has changed or if Playwright was blocked. "
            "Try enabling **Headless Browser** in the sidebar, or retry."
        )
        return pd.DataFrame()

    processor = DataProcessor(
        enable_skip_tracing=config["skip_tracing"],
        max_skip_trace_per_batch=20,
    )
    with st.spinner("Processing and enriching data..."):
        df = processor.process(all_records)

    st.session_state[partial_key] = df
    st.session_state[results_key] = df
    return df


def save_results_csv(df: pd.DataFrame, lead_type: LeadType, label: str) -> Path:
    """Persist the current result set to the local exports folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.strip().lower().replace(" ", "_")
    if not safe_label:
        safe_label = lead_type.name.lower()
    output_path = Path("exports") / f"prime_coastal_leads_{safe_label}_{timestamp}.csv"
    return CSVExporter.to_file(df, output_path)


def build_outreach_view(df: pd.DataFrame) -> pd.DataFrame:
    """Return a simplified outreach-first view of the lead table."""
    visible_columns = [col for col in OUTREACH_PRIORITY_COLUMNS if col in df.columns]
    return df[visible_columns].copy()


def render_metrics(df: pd.DataFrame):
    """Render top-level lead summary metrics."""
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Records", len(df))
    email_col = "Scraped Emails"
    emails_found = int(df[email_col].astype(bool).sum()) if email_col in df.columns else 0
    m2.metric("Records with Emails", emails_found)
    counties_col = "County"
    county_count = df[counties_col].nunique() if counties_col in df.columns else 0
    m3.metric("Counties Scraped", county_count)
    absentee_col = "Absentee Owner"
    absentee_count = (
        int(df[absentee_col].fillna(False).astype(bool).sum())
        if absentee_col in df.columns
        else 0
    )
    m4.metric("Absentee Owners", absentee_count)


def render_results_table(df: pd.DataFrame):
    """Render outreach table, full detail, CSV download, and county breakdown."""
    display_df = df.copy()
    if "Lead Score" in display_df.columns:
        display_df = display_df.sort_values(
            by=["Lead Score", "Last Sale Date"],
            ascending=[False, False],
            na_position="last",
        )
    elif "Est Equity Pct" in display_df.columns:
        display_df = display_df.sort_values(
            by="Est Equity Pct",
            ascending=False,
            na_position="last",
        )

    outreach_df = build_outreach_view(display_df)
    st.caption("Outreach-first view")
    st.dataframe(outreach_df, width="stretch", hide_index=True)

    with st.expander("Full Detail View", expanded=False):
        st.dataframe(display_df, width="stretch", hide_index=True)

    st.divider()
    csv_bytes = CSVExporter.to_bytes(df)
    st.download_button(
        label="Download CSV",
        data=csv_bytes,
        file_name="prime_coastal_leads.csv",
        mime="text/csv",
        type="secondary",
        width="content",
    )

    counties_col = "County"
    if counties_col in df.columns and df[counties_col].nunique() > 1:
        st.subheader("County Breakdown")
        breakdown = (
            df.groupby(counties_col)
            .size()
            .reset_index(name="Records")
            .sort_values("Records", ascending=False)
        )
        st.bar_chart(breakdown.set_index(counties_col), width="stretch")


def render_county_sidebar(default=["Sarasota"]) -> dict:
    """Render shared county/max/headless/skip controls."""
    st.sidebar.image("https://img.icons8.com/fluency/96/beach.png", width=64)
    st.sidebar.title("Prime Coastal Funding")
    st.sidebar.caption("OSINT Lead Generation Platform")
    st.sidebar.divider()

    st.sidebar.subheader("Configuration")
    selected_counties = st.sidebar.multiselect(
        "Florida Counties",
        options=list(COUNTY_SCRAPERS.keys()),
        default=default,
        key="shared_counties",
        help="Select one or more counties to scrape.",
    )
    max_results = st.sidebar.slider(
        "Max Records per County",
        min_value=5,
        max_value=200,
        value=50,
        step=5,
        key="shared_max_results",
        help="Soft cap on results returned per county scraper run.",
    )
    headless_mode = st.sidebar.checkbox(
        "Headless Browser",
        value=False,
        key="shared_headless",
        help=(
            "Uncheck (default) for headful mode - shows the browser window "
            "and is less likely to be blocked by government portals."
        ),
    )
    skip_tracing = st.sidebar.checkbox(
        "Enable Skip Tracing",
        value=False,
        key="shared_skip_tracing",
        help=(
            "Run Google Dorking to find email addresses for each owner. "
            "This is slow (~10-20 s per owner). Disable for quick test runs."
        ),
    )

    st.sidebar.divider()
    st.sidebar.info(
        "All data is sourced from **free public government records**. "
        "No paid APIs are used."
    )

    return {
        "counties": selected_counties,
        "max_results": max_results,
        "headless": headless_mode,
        "skip_tracing": skip_tracing,
    }
