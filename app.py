"""
Prime Coastal Funding — OSINT Lead Generation Dashboard
========================================================

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import logging
import traceback

import pandas as pd
import streamlit as st

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
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Streamlit page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Prime Coastal Funding – OSINT Lead Gen",
    page_icon="🏖️",
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
    LeadType.FLIPPER: (
        "Properties with **2+ deed transfers within 12 months** — "
        "likely fix-and-flip investors who may need short-term bridge financing."
    ),
    LeadType.HIGH_INTEREST: (
        "Mortgage Deeds recorded in **2022–2023** (peak rate era) or properties "
        "with **no recorded mortgage in the last 20 years** — strong DSCR / "
        "refinance candidates."
    ),
    LeadType.PAST_FINANCING: (
        "Records showing **Certificate of Title** or **Satisfaction of Mortgage** "
        "— owners who recently cleared a lien and may be open to new financing."
    ),
}


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def render_sidebar() -> dict:
    """Render sidebar controls and return the user's selections."""
    st.sidebar.image(
        "https://img.icons8.com/fluency/96/beach.png",
        width=64,
    )
    st.sidebar.title("Prime Coastal Funding")
    st.sidebar.caption("OSINT Lead Generation Platform")
    st.sidebar.divider()

    st.sidebar.subheader("⚙️ Configuration")

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
            "Uncheck (default) for headful mode — shows the browser window "
            "and is less likely to be blocked by government portals."
        ),
    )

    skip_tracing = st.sidebar.checkbox(
        "Enable Skip Tracing",
        value=False,
        help=(
            "Run Google Dorking to find email addresses for each owner. "
            "This is slow (~10–20 s per owner). Disable for quick test runs."
        ),
    )

    st.sidebar.divider()
    st.sidebar.info(
        "ℹ️ All data is sourced from **free public government records**. "
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
    with st.expander(f"ℹ️ About '{lead_type.value}' leads", expanded=False):
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
    progress_bar = st.progress(0, text="Initialising scrapers…")
    status = st.status("Running scrapers…", expanded=True)

    for idx, county_name in enumerate(counties):
        scraper_cls = COUNTY_SCRAPERS[county_name]
        status.write(f"🔍 Scraping **{county_name}** county…")
        try:
            with scraper_cls(headless=headless) as scraper:
                records = scraper.fetch_records(lead_type, max_results=max_results)
                all_records.extend(records)
                status.write(
                    f"✅ {county_name}: found **{len(records)}** record(s)."
                )
        except Exception as exc:
            status.write(f"❌ {county_name} scraper failed: `{exc}`")
            logger.error("Scraper %s failed: %s", county_name, traceback.format_exc())

        progress_bar.progress(
            (idx + 1) / len(counties),
            text=f"Processed {idx + 1}/{len(counties)} counties",
        )

    status.update(label="Scraping complete!", state="complete")
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

    with st.spinner("Processing and enriching data…"):
        df = processor.process(all_records)

    return df


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def main():
    # ---- Header ----
    st.title("🏖️ Prime Coastal Funding — OSINT Lead Generator")
    st.markdown(
        "Generate **commercial real estate leads** from Florida public property "
        "records and enrich them with skip-traced contact information — "
        "**no paid APIs required**."
    )

    # ---- Sidebar ----
    config = render_sidebar()
    render_lead_type_info(config["lead_type"])

    st.divider()

    # ---- Controls ----
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        generate = st.button(
            "🚀 Generate Leads",
            type="primary",
            use_container_width=True,
        )

    with col_info:
        st.markdown(
            f"**Selected:** {', '.join(config['counties']) or 'None'} | "
            f"**Lead type:** {config['lead_type'].value} | "
            f"**Max per county:** {config['max_results']}"
        )

    # ---- Results area (persisted in session state) ----
    if "results_df" not in st.session_state:
        st.session_state["results_df"] = pd.DataFrame()

    if generate:
        st.session_state["results_df"] = run_scrapers(config)

    df: pd.DataFrame = st.session_state["results_df"]

    if df.empty:
        st.info(
            "Click **🚀 Generate Leads** to start scraping. "
            "Results will appear here."
        )
        return

    # ---- Metrics ----
    st.subheader("📊 Results")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Records", len(df))
    email_col = "Scraped Emails"
    emails_found = int(df[email_col].astype(bool).sum()) if email_col in df.columns else 0
    m2.metric("Records with Emails", emails_found)
    counties_col = "County"
    county_count = df[counties_col].nunique() if counties_col in df.columns else 0
    m3.metric("Counties Scraped", county_count)

    # ---- Data table ----
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    # ---- Download ----
    st.divider()
    csv_bytes = CSVExporter.to_bytes(df)
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_bytes,
        file_name="prime_coastal_leads.csv",
        mime="text/csv",
        type="secondary",
        use_container_width=False,
    )

    # ---- Per-county breakdown ----
    if counties_col in df.columns and df[counties_col].nunique() > 1:
        st.subheader("County Breakdown")
        breakdown = (
            df.groupby(counties_col)
            .size()
            .reset_index(name="Records")
            .sort_values("Records", ascending=False)
        )
        st.bar_chart(breakdown.set_index(counties_col))


if __name__ == "__main__":
    main()
