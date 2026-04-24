from __future__ import annotations

import pandas as pd
import streamlit as st

from scrapers.base_scraper import LeadType
from utils.lead_app_utils import (
    LEAD_TYPE_HELP,
    render_county_sidebar,
    render_metrics,
    render_results_table,
    run_scrapers,
    save_results_csv,
)

st.set_page_config(
    page_title="Mortgage Mod Refi - Prime Coastal Funding",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.title("Prime Coastal Funding - Mortgage Mod Refi Generator")
    st.warning("🔧 In Tuning")
    st.warning(
        "This lead generator is currently being fine-tuned. "
        "Results may be incomplete or require manual review."
    )

    config = render_county_sidebar(default=["Sarasota"])
    lead_type = LeadType.MORTGAGE_MOD

    with st.sidebar.expander("Detection Criteria", expanded=False):
        st.markdown(
            "- Searches for **MORTGAGE MOD AGREEMT** documents filed "
            "**1/1/2025 → today** at the Sarasota Clerk of Court\n"
            "- Each PDF is OCR-scanned for: borrower name, modified principal, "
            "interest rate, maturity date, balloon/HELOC signals\n"
            "- Targets are prime refi candidates — they already needed a modification once"
        )

    with st.expander(f"About '{lead_type.value}' leads", expanded=False):
        st.markdown(LEAD_TYPE_HELP[lead_type])

    st.divider()

    tab_leads, = st.tabs(["Lead Generator"])

    with tab_leads:
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            generate = st.button("Generate Leads", type="primary", use_container_width=True)

        with col_info:
            st.markdown(
                f"**Selected:** {', '.join(config['counties']) or 'None'} | "
                f"**Lead type:** {lead_type.value} | "
                f"**Max per county:** {config['max_results']}"
            )

        if "mortgage_mod_results_df" not in st.session_state:
            st.session_state["mortgage_mod_results_df"] = pd.DataFrame()
        if "mortgage_mod_saved_csv_path" not in st.session_state:
            st.session_state["mortgage_mod_saved_csv_path"] = ""

        if generate:
            run_config = {**config, "lead_type": lead_type}
            st.session_state["mortgage_mod_results_df"] = run_scrapers(run_config)
            if not st.session_state["mortgage_mod_results_df"].empty:
                saved_path = save_results_csv(
                    st.session_state["mortgage_mod_results_df"],
                    lead_type,
                    label="mortgage_mod_refi",
                )
                st.session_state["mortgage_mod_saved_csv_path"] = str(saved_path)
            else:
                st.session_state["mortgage_mod_saved_csv_path"] = ""

        df: pd.DataFrame = st.session_state["mortgage_mod_results_df"]

        if df.empty:
            st.info(
                "Click **Generate Leads** to start scraping. "
                "Results will appear here."
            )
        else:
            st.subheader("Results")
            saved_csv_path = st.session_state.get("mortgage_mod_saved_csv_path", "")
            if saved_csv_path:
                st.caption(f"Saved to `{saved_csv_path}`")
            render_metrics(df)
            if "Sales Strategy" in df.columns and not df["Sales Strategy"].isna().all():
                st.subheader("Lead Strategy Breakdown")
                strategy_counts = df["Sales Strategy"].value_counts()
                s_cols = st.columns(min(len(strategy_counts), 4))
                for i, (strategy, count) in enumerate(strategy_counts.items()):
                    s_cols[i % 4].metric(strategy[:35], int(count))
            render_results_table(df)


if __name__ == "__main__":
    main()
