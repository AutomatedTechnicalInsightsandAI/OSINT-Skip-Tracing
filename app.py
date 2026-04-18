"""
Prime Coastal Funding - OSINT Lead Generation Dashboard
=======================================================

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from ads.ad_streamlit_tab import render_ads_tab
from contracts.contracts_streamlit_tab import render_contracts_tab
from financials.financial_streamlit_tab import render_financial_tab
from ghl.ghl_streamlit_tab import render_ghl_tab
from scrapers.base_scraper import LeadType
from scrapers.broward_scraper import BrowardScraper
from scrapers.miami_dade_scraper import MiamiDadeScraper
from scrapers.sarasota_scraper import SarasotaScraper
from utils.csv_exporter import CSVExporter
from utils.data_processor import DataProcessor

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Streamlit page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Prime Coastal Funding - OSINT Lead Gen",
    page_icon="PCF",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Scraper registry
# ---------------------------------------------------------------------------
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
        "Merged balloon/refi target: includes (1) Sarasota mortgage records with OCR-confirmed "
        "maturity dates in the next 12 months and commercial debt signals (entity borrowers, "
        "commercial loan language, or matched commercial parcel data); AND (2) commercial "
        "property with personal-name borrowers, no current exemption, balloon maturity due within "
        "6 months, and OCR-detected note rate of 8% or higher."
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


def render_sidebar() -> dict:
    """Render sidebar controls and return the user's selections."""
    st.sidebar.image(
        "https://img.icons8.com/fluency/96/beach.png",
        width=64,
    )
    st.sidebar.title("Prime Coastal Funding")
    st.sidebar.caption("OSINT Lead Generation Platform")
    st.sidebar.divider()

    st.sidebar.subheader("Configuration")

    selected_counties = st.sidebar.multiselect(
        "Florida Counties",
        options=list(COUNTY_SCRAPERS.keys()),
        default=["Sarasota"],
        help="Select one or more counties to scrape.",
    )

    lead_type_label = st.sidebar.selectbox(
        "Lead Type",
        options=[lt.value for lt in LeadType],
        index=0,
        help="Choose the category of leads to generate.",
    )

    max_results = st.sidebar.slider(
        "Max Records per County",
        min_value=5,
        max_value=200,
        value=50,
        step=5,
        help="Soft cap on results returned per county scraper run.",
    )

    headless_mode = st.sidebar.checkbox(
        "Headless Browser",
        value=False,
        help=(
            "Uncheck (default) for headful mode - shows the browser window "
            "and is less likely to be blocked by government portals."
        ),
    )

    skip_tracing = st.sidebar.checkbox(
        "Enable Skip Tracing",
        value=False,
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
        "lead_type": next(lt for lt in LeadType if lt.value == lead_type_label),
        "max_results": max_results,
        "headless": headless_mode,
        "skip_tracing": skip_tracing,
    }


def render_lead_type_info(lead_type: LeadType):
    """Render an informational expander for the selected lead type."""
    with st.expander(f"About '{lead_type.value}' leads", expanded=False):
        st.markdown(LEAD_TYPE_HELP[lead_type])


def run_scrapers(config: dict) -> pd.DataFrame:
    """Execute scrapers for all selected counties and return merged DataFrame."""
    counties: list[str] = config["counties"]
    lead_type: LeadType = config["lead_type"]
    max_results: int = config["max_results"]
    headless: bool = config["headless"]

    if not counties:
        st.warning("Please select at least one county in the sidebar.")
        return pd.DataFrame()

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

    return df


def save_results_csv(df: pd.DataFrame, lead_type: LeadType) -> Path:
    """Persist the current result set to the local exports folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_lead_type = (
        lead_type.name.lower()
        .replace(" ", "_")
    )
    output_path = Path("exports") / f"prime_coastal_leads_{safe_lead_type}_{timestamp}.csv"
    return CSVExporter.to_file(df, output_path)


def build_outreach_view(df: pd.DataFrame) -> pd.DataFrame:
    """Return a simplified outreach-first view of the lead table."""
    visible_columns = [col for col in OUTREACH_PRIORITY_COLUMNS if col in df.columns]
    return df[visible_columns].copy()


def main():
    st.title("Prime Coastal Funding - OSINT Lead Generator")
    st.markdown(
        "Generate **commercial real estate leads** from Florida public property "
        "records and enrich them with skip-traced contact information - "
        "**no paid APIs required**."
    )

    config = render_sidebar()
    render_lead_type_info(config["lead_type"])

    st.divider()

    tab_leads, tab_ghl, tab_ads, tab_contracts, tab_financials = st.tabs(
        [
            "Lead Generator",
            "Push to GHL",
            "Ad Templates",
            "Contracts & Disputes",
            "Financial Model",
        ]
    )

    with tab_leads:
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            generate = st.button(
                "Generate Leads",
                type="primary",
                width="stretch",
            )

        with col_info:
            st.markdown(
                f"**Selected:** {', '.join(config['counties']) or 'None'} | "
                f"**Lead type:** {config['lead_type'].value} | "
                f"**Max per county:** {config['max_results']}"
            )

        if "results_df" not in st.session_state:
            st.session_state["results_df"] = pd.DataFrame()
        if "saved_csv_path" not in st.session_state:
            st.session_state["saved_csv_path"] = ""

        if generate:
            st.session_state["results_df"] = run_scrapers(config)
            if not st.session_state["results_df"].empty:
                saved_path = save_results_csv(
                    st.session_state["results_df"],
                    config["lead_type"],
                )
                st.session_state["saved_csv_path"] = str(saved_path)
            else:
                st.session_state["saved_csv_path"] = ""

        df: pd.DataFrame = st.session_state["results_df"]

        if df.empty:
            st.info(
                "Click **Generate Leads** to start scraping. "
                "Results will appear here."
            )
        else:
            st.subheader("Results")
            saved_csv_path = st.session_state.get("saved_csv_path", "")
            if saved_csv_path:
                st.caption(f"Saved to `{saved_csv_path}`")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Records", len(df))
            email_col = "Scraped Emails"
            emails_found = (
                int(df[email_col].astype(bool).sum()) if email_col in df.columns else 0
            )
            m2.metric("Records with Emails", emails_found)
            counties_col = "County"
            county_count = (
                df[counties_col].nunique() if counties_col in df.columns else 0
            )
            m3.metric("Counties Scraped", county_count)
            absentee_col = "Absentee Owner"
            absentee_count = (
                int(df[absentee_col].fillna(False).astype(bool).sum())
                if absentee_col in df.columns
                else 0
            )
            m4.metric("Absentee Owners", absentee_count)

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
            st.dataframe(
                outreach_df,
                width="stretch",
                hide_index=True,
            )

            with st.expander("Full Detail View", expanded=False):
                st.dataframe(
                    display_df,
                    width="stretch",
                    hide_index=True,
                )

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

            if counties_col in df.columns and df[counties_col].nunique() > 1:
                st.subheader("County Breakdown")
                breakdown = (
                    df.groupby(counties_col)
                    .size()
                    .reset_index(name="Records")
                    .sort_values("Records", ascending=False)
                )
                st.bar_chart(breakdown.set_index(counties_col), width="stretch")

    df = st.session_state.get("results_df", pd.DataFrame())

    with tab_ghl:
        render_ghl_tab(df)

    with tab_ads:
        render_ads_tab(df)

    with tab_contracts:
        render_contracts_tab(df)

    with tab_financials:
        render_financial_tab(df)


if __name__ == "__main__":
    main()
