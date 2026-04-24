from __future__ import annotations

import pandas as pd
import streamlit as st

from ads.ad_streamlit_tab import render_ads_tab
from contracts.contracts_streamlit_tab import render_contracts_tab
from financials.financial_streamlit_tab import render_financial_tab
from ghl.ghl_streamlit_tab import render_ghl_tab
from scrapers.base_scraper import LeadType
from utils.lead_app_utils import (
    LEAD_TYPE_HELP,
    render_county_sidebar,
    render_download_leads_so_far,
    render_metrics,
    render_results_table,
    run_scrapers,
    save_results_csv,
)

st.set_page_config(
    page_title="Cash-Out Refi - Prime Coastal Funding",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.title("Prime Coastal Funding - Cash-Out Refi Generator")
    st.success("✅ Production")
    st.markdown(
        "Generate **commercial real estate leads** from Florida public property "
        "records and enrich them with skip-traced contact information - "
        "**no paid APIs required**."
    )

    config = render_county_sidebar(default=["Sarasota"])
    lead_type = LeadType.CASHOUT_REFI

    with st.expander(f"About '{lead_type.value}' leads", expanded=False):
        st.markdown(LEAD_TYPE_HELP[lead_type])

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
            generate = st.button("Generate Leads", type="primary", width="stretch")

        with col_info:
            st.markdown(
                f"**Selected:** {', '.join(config['counties']) or 'None'} | "
                f"**Lead type:** {lead_type.value} | "
                f"**Max per county:** {config['max_results']}"
            )

        if "cashout_results_df" not in st.session_state:
            st.session_state["cashout_results_df"] = pd.DataFrame()
        if "cashout_partial_df" not in st.session_state:
            st.session_state["cashout_partial_df"] = pd.DataFrame()
        if "cashout_saved_csv_path" not in st.session_state:
            st.session_state["cashout_saved_csv_path"] = ""

        render_download_leads_so_far(
            results_key="cashout_results_df",
            partial_key="cashout_partial_df",
            filename_prefix="cashout_refi",
            widget_key="cashout_download_so_far_top",
        )

        if generate:
            run_config = {**config, "lead_type": lead_type}
            st.session_state["cashout_results_df"] = run_scrapers(run_config)
            if not st.session_state["cashout_results_df"].empty:
                saved_path = save_results_csv(
                    st.session_state["cashout_results_df"],
                    lead_type,
                    label="cashout_refi",
                )
                st.session_state["cashout_saved_csv_path"] = str(saved_path)
            else:
                st.session_state["cashout_saved_csv_path"] = ""

        df: pd.DataFrame = st.session_state["cashout_results_df"]

        if df.empty:
            st.info(
                "Click **Generate Leads** to start scraping. "
                "Results will appear here."
            )
        else:
            st.subheader("Results")
            saved_csv_path = st.session_state.get("cashout_saved_csv_path", "")
            if saved_csv_path:
                st.caption(f"Saved to `{saved_csv_path}`")
            render_metrics(df)
            render_results_table(df)
            render_download_leads_so_far(
                results_key="cashout_results_df",
                partial_key="cashout_partial_df",
                filename_prefix="cashout_refi",
                widget_key="cashout_download_so_far_bottom",
            )

    df = st.session_state.get("cashout_results_df", pd.DataFrame())

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
