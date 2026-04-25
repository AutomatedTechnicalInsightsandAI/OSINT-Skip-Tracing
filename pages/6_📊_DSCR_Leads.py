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
    page_title="DSCR Investor Leads - Prime Coastal Funding",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.title("Prime Coastal Funding - DSCR Investor Leads")
    st.info("✅ Active")

    config = render_county_sidebar(default=["Sarasota"])
    lead_type = LeadType.DSCR

    with st.sidebar.expander("Detection Criteria", expanded=False):
        st.markdown(
            "- Pulls up to **500 properties** per run from the Sarasota Property Appraiser CSV export\n"
            "- **No absentee-owner filter** — all ownership types included\n"
            "- **No interest-rate filter** — all rate environments included\n"
            "- DSCR estimated: monthly rent = 0.70% of Just Value; payment at 75% LTV, 7.00%, 30 yr\n"
            "- Sort by **DSCR Ratio ↓** to find strongest cash-flow deals first"
        )

    with st.expander(f"About '{lead_type.value}' leads", expanded=False):
        st.markdown(LEAD_TYPE_HELP[lead_type])

    st.divider()

    (tab_leads,) = st.tabs(["Lead Generator"])

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

        if "dscr_results_df" not in st.session_state:
            st.session_state["dscr_results_df"] = pd.DataFrame()
        if "dscr_saved_csv_path" not in st.session_state:
            st.session_state["dscr_saved_csv_path"] = ""

        if generate:
            run_config = {**config, "lead_type": lead_type}
            st.session_state["dscr_results_df"] = run_scrapers(run_config)
            if not st.session_state["dscr_results_df"].empty:
                saved_path = save_results_csv(
                    st.session_state["dscr_results_df"],
                    lead_type,
                    label="dscr_investor",
                )
                st.session_state["dscr_saved_csv_path"] = str(saved_path)
            else:
                st.session_state["dscr_saved_csv_path"] = ""

        df: pd.DataFrame = st.session_state["dscr_results_df"]

        if df.empty:
            st.info(
                "Click **Generate Leads** to start scraping. "
                "Results will appear here."
            )
        else:
            st.subheader("Results")
            saved_csv_path = st.session_state.get("dscr_saved_csv_path", "")
            if saved_csv_path:
                st.caption(f"Saved to `{saved_csv_path}`")
            render_metrics(df)

            if "DSCR Ratio" in df.columns:
                above_125 = int(
                    (pd.to_numeric(df["DSCR Ratio"], errors="coerce") >= 1.25).sum()
                )
                above_100 = int(
                    (pd.to_numeric(df["DSCR Ratio"], errors="coerce") >= 1.0).sum()
                )
                d1, d2 = st.columns(2)
                d1.metric("DSCR ≥ 1.25 (lendable)", above_125)
                d2.metric("DSCR ≥ 1.00 (positive cash flow)", above_100)

            if "Sales Strategy" in df.columns and not df["Sales Strategy"].isna().all():
                st.subheader("Lead Strategy Breakdown")
                strategy_counts = df["Sales Strategy"].value_counts()
                s_cols = st.columns(min(len(strategy_counts), 4))
                for i, (strategy, count) in enumerate(strategy_counts.items()):
                    s_cols[i % 4].metric(strategy[:35], int(count))

            render_results_table(df)


if __name__ == "__main__":
    main()
