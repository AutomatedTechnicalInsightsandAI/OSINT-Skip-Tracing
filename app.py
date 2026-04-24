"""
Prime Coastal Funding - OSINT Lead Generation Dashboard
=======================================================

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from scrapers.base_scraper import LeadType
from utils.lead_app_utils import LEAD_TYPE_HELP, render_county_sidebar

st.set_page_config(
    page_title="Prime Coastal Funding - OSINT Lead Gen",
    page_icon="PCF",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.title("Prime Coastal Funding - OSINT Lead Generator")
    st.markdown(
        "Welcome to the lead generation hub. Use the page navigation on the left "
        "to run one isolated lead generator at a time."
    )

    shared_config = render_county_sidebar(default=["Sarasota"])
    st.session_state["global_lead_config"] = shared_config

    st.divider()
    st.subheader("Lead Generators")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("### 💰 Cash-Out Refi")
        st.success("✅ Production")
        with st.expander("About this generator", expanded=False):
            st.markdown(LEAD_TYPE_HELP[LeadType.CASHOUT_REFI])

    with col2:
        st.markdown("### 🎈 Balloon Balance")
        st.warning("🔧 In Tuning")
        with st.expander("About this generator", expanded=False):
            st.markdown(LEAD_TYPE_HELP[LeadType.BALLOON_PROSPECTS])

    with col3:
        st.markdown("### 🏛️ Trust Refi")
        st.warning("🔧 In Tuning")
        with st.expander("About this generator", expanded=False):
            st.markdown(LEAD_TYPE_HELP[LeadType.TRUST_REFI])

    with col4:
        st.markdown("### 📋 CSV Skip-Trace")
        st.success("✅ Production")
        st.markdown(
            "Upload a CSV of owner names to batch skip-trace for phones and emails."
        )

    st.info(
        "This home page does not run scrapers. Open one of the dedicated pages "
        "from the sidebar navigation to generate leads."
    )


if __name__ == "__main__":
    main()
