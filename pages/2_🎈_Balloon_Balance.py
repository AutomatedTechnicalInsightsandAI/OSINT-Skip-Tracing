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
    page_title="Balloon Balance - Prime Coastal Funding",
    page_icon="🎈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.title("Prime Coastal Funding - Balloon Balance Generator")
    st.warning("🔧 In Tuning")
    st.warning(
        "This lead generator is currently being fine-tuned. "
        "Results may be incomplete or require manual review."
    )

    config = render_county_sidebar(default=["Sarasota"])
    lead_type = LeadType.BALLOON_PROSPECTS

    with st.sidebar.expander("Tuning Notes", expanded=False):
        st.sidebar.text_area("Tuning Notes", key="balloon_notes")

    with st.expander(f"About '{lead_type.value}' leads", expanded=False):
        st.markdown(LEAD_TYPE_HELP[lead_type])

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        generate = st.button("Generate Leads", type="primary", width="stretch")
    with col_info:
        st.markdown(
            f"**Selected:** {', '.join(config['counties']) or 'None'} | "
            f"**Lead type:** {lead_type.value} | "
            f"**Max per county:** {config['max_results']}"
        )

    if "balloon_results_df" not in st.session_state:
        st.session_state["balloon_results_df"] = pd.DataFrame()
    if "balloon_saved_csv_path" not in st.session_state:
        st.session_state["balloon_saved_csv_path"] = ""

    if generate:
        run_config = {**config, "lead_type": lead_type}
        st.session_state["balloon_results_df"] = run_scrapers(run_config)
        if not st.session_state["balloon_results_df"].empty:
            saved_path = save_results_csv(
                st.session_state["balloon_results_df"],
                lead_type,
                label="balloon_balance",
            )
            st.session_state["balloon_saved_csv_path"] = str(saved_path)
        else:
            st.session_state["balloon_saved_csv_path"] = ""

    df: pd.DataFrame = st.session_state["balloon_results_df"]

    if df.empty:
        st.info("Click **Generate Leads** to start scraping. Results will appear here.")
        return

    st.subheader("Results")
    saved_csv_path = st.session_state.get("balloon_saved_csv_path", "")
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
