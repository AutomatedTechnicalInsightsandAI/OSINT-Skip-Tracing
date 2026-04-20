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
    page_title="Trust Refi - Prime Coastal Funding",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.title("Prime Coastal Funding - Trust Refi Generator")
    st.warning("🔧 In Tuning")
    st.warning(
        "This lead generator is currently being fine-tuned. "
        "Results may be incomplete or require manual review."
    )

    config = render_county_sidebar(default=["Sarasota"])
    lead_type = LeadType.TRUST_REFI

    with st.sidebar.expander("Trust Detection Criteria", expanded=False):
        st.markdown(
            "- Owner name contains **Trust**, **Trustee**, or **TR**\n"
            "- Deed type contains trust terms such as **trustee's deed**\n"
            "- Any title/deed language that indicates property is held by a trust entity"
        )

    with st.sidebar.expander("Tuning Notes", expanded=False):
        st.sidebar.text_area("Tuning Notes", key="trust_notes")

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

    if "trust_results_df" not in st.session_state:
        st.session_state["trust_results_df"] = pd.DataFrame()
    if "trust_saved_csv_path" not in st.session_state:
        st.session_state["trust_saved_csv_path"] = ""

    if generate:
        run_config = {**config, "lead_type": lead_type}
        st.session_state["trust_results_df"] = run_scrapers(run_config)
        if not st.session_state["trust_results_df"].empty:
            saved_path = save_results_csv(
                st.session_state["trust_results_df"],
                lead_type,
                label="trust_refi",
            )
            st.session_state["trust_saved_csv_path"] = str(saved_path)
        else:
            st.session_state["trust_saved_csv_path"] = ""

    df: pd.DataFrame = st.session_state["trust_results_df"]

    if df.empty:
        st.info("Click **Generate Leads** to start scraping. Results will appear here.")
        return

    st.subheader("Results")
    saved_csv_path = st.session_state.get("trust_saved_csv_path", "")
    if saved_csv_path:
        st.caption(f"Saved to `{saved_csv_path}`")
    render_metrics(df)
    render_results_table(df)


if __name__ == "__main__":
    main()
