"""
Streamlit tab for the Ad Templates module.

Renders a three-section ad campaign dashboard:
1. Campaign Generator  — build Google + Meta campaign packages
2. Budget ROI Calculator — model expected return on ad spend
3. Keyword Planner — browse and export keyword lists by sub-vertical
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from ads.ad_copy_generator import AdCopyGenerator
from ads.campaign_builder import CampaignBuilder
from ads.targeting_config import TargetingConfig

_generator = AdCopyGenerator()
_builder = CampaignBuilder()

# ---------------------------------------------------------------------------
# Vertical / sub-vertical options
# ---------------------------------------------------------------------------
_VERTICAL_OPTIONS: dict[str, list[str]] = {
    "Home Services": ["hvac", "roofing", "solar", "plumbing", "electrical", "water_damage", "windows", "pest_control"],
    "Real Estate": ["dscr_loan", "hard_money", "fix_and_flip", "bridge_loan", "commercial_re", "wholesale_buyer"],
    "B2B": ["smb", "mid_market", "enterprise"],
}

_VERTICAL_KEY: dict[str, str] = {
    "Home Services": "home_services",
    "Real Estate": "real_estate",
    "B2B": "b2b",
}

_SUB_VERTICAL_LABELS: dict[str, str] = {
    "hvac": "HVAC",
    "roofing": "Roofing",
    "solar": "Solar",
    "plumbing": "Plumbing",
    "electrical": "Electrical",
    "water_damage": "Water Damage",
    "windows": "Windows",
    "pest_control": "Pest Control",
    "dscr_loan": "DSCR Loan",
    "hard_money": "Hard Money",
    "fix_and_flip": "Fix & Flip",
    "bridge_loan": "Bridge Loan",
    "commercial_re": "Commercial RE",
    "wholesale_buyer": "Wholesale Buyer",
    "smb": "SMB",
    "mid_market": "Mid-Market",
    "enterprise": "Enterprise",
}

_METRO_OPTIONS = list(TargetingConfig.FLORIDA_METROS.keys())

# Estimated CPC ranges per sub-vertical (for keyword planner display)
_ESTIMATED_CPC: dict[str, float] = {
    "hvac": 32.0,
    "roofing": 40.0,
    "solar": 48.0,
    "plumbing": 24.0,
    "electrical": 28.0,
    "water_damage": 52.0,
    "windows": 31.0,
    "pest_control": 17.0,
    "dscr_loan": 62.0,
    "hard_money": 76.0,
    "fix_and_flip": 52.0,
    "bridge_loan": 68.0,
    "commercial_re": 115.0,
    "wholesale_buyer": 36.0,
    "smb": 26.0,
    "mid_market": 85.0,
    "enterprise": 190.0,
}


def render_ads_tab(df: pd.DataFrame) -> None:
    """
    Render the 📢 Ad Templates tab inside the main Streamlit dashboard.

    Args:
        df: Lead results DataFrame from session state (may be empty).
    """
    st.header("📢 Ad Campaign Templates")
    st.caption(
        "Generate production-ready Google and Meta ad campaign packages, "
        "model your ROI, and export keyword lists for every sub-vertical."
    )

    # ======================================================================
    # Section 1 — Campaign Generator
    # ======================================================================
    st.subheader("🎯 Campaign Generator")

    col_vert, col_sub, col_metro = st.columns(3)

    with col_vert:
        vertical_label = st.selectbox(
            "Vertical",
            options=list(_VERTICAL_OPTIONS.keys()),
            key="ads_vertical",
        )

    with col_sub:
        sub_options = _VERTICAL_OPTIONS[vertical_label]
        sub_labels = [_SUB_VERTICAL_LABELS.get(s, s) for s in sub_options]
        sub_label_sel = st.selectbox(
            "Sub-Vertical",
            options=sub_labels,
            key="ads_sub_vertical",
        )
        # Map label back to key
        sub_vertical = sub_options[sub_labels.index(sub_label_sel)]

    with col_metro:
        metro = st.selectbox(
            "Florida Metro",
            options=_METRO_OPTIONS,
            key="ads_metro",
        )

    monthly_budget = st.number_input(
        "Monthly Budget ($)",
        min_value=500.0,
        max_value=50_000.0,
        value=3_000.0,
        step=500.0,
        key="ads_budget",
    )

    if st.button("Generate Campaign Package", type="primary", key="ads_generate"):
        vertical_key = _VERTICAL_KEY[vertical_label]
        with st.spinner("Building campaign package…"):
            package = _builder.build_full_campaign_package(
                vertical=vertical_key,
                sub_vertical=sub_vertical,
                location=metro,
                monthly_budget=monthly_budget,
            )
        st.session_state["ads_package"] = package

    # Display package if available
    if "ads_package" in st.session_state:
        package = st.session_state["ads_package"]
        google = package["google_campaign"]
        meta = package["meta_campaign"]
        budget_split = package["budget_split"]

        # Metrics
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Monthly Budget", f"${package['monthly_budget']:,.0f}")
        m2.metric("Google Budget", f"${budget_split['google_monthly']:,.0f}")
        m3.metric("Meta Budget", f"${budget_split['meta_monthly']:,.0f}")
        m4.metric("Est. Leads/Month", str(package["expected_metrics"]["estimated_leads"]))

        # Google RSA
        with st.expander("📣 Google Responsive Search Ad", expanded=True):
            st.markdown(f"**Campaign:** {google['campaign_name']}")
            st.markdown(f"**Bid Strategy:** {google['bid_strategy']} — Target CPA: **${google['target_cpa']:,.0f}**")
            st.markdown("**Headlines** *(15 — Google selects the best combinations)*")
            hl_cols = st.columns(3)
            for i, headline in enumerate(google["headlines"]):
                hl_cols[i % 3].code(headline)
            st.markdown("**Descriptions**")
            for desc in google["descriptions"]:
                st.info(desc)
            st.markdown(f"**Keywords:** {', '.join(google['keywords'])}")
            st.markdown(f"**Negative Keywords:** {', '.join(google['negative_keywords'])}")

        # Meta ad
        with st.expander("📘 Meta (Facebook / Instagram) Ad — Variant A", expanded=False):
            st.markdown(f"**Campaign:** {meta['campaign_name']}")
            st.markdown("**Primary Text**")
            st.text_area("", value=meta["primary_text"], height=130, disabled=True, key="meta_primary_a")
            col_a, col_b = st.columns(2)
            col_a.markdown(f"**Headline:** {meta['headline']}")
            col_b.markdown(f"**Description:** {meta['description']}")
            st.markdown(f"**Call to Action:** `{meta['call_to_action']}`")
            st.markdown(f"**Placements:** {', '.join(meta['placements'])}")

        # Meta Variant B
        ab = package["ab_test_variant"]
        with st.expander("🔄 Meta Ad — Variant B (A/B Test)", expanded=False):
            st.markdown(f"**Campaign:** {ab['campaign_name']}")
            st.markdown("**Primary Text**")
            st.text_area("", value=ab["primary_text"], height=130, disabled=True, key="meta_primary_b")
            col_a2, col_b2 = st.columns(2)
            col_a2.markdown(f"**Headline:** {ab['headline']}")
            col_b2.markdown(f"**Description:** {ab['description']}")
            st.markdown(f"**Call to Action:** `{ab['call_to_action']}`")

        # Landing page recs
        with st.expander("🏁 Landing Page Recommendations", expanded=False):
            for rec in package["landing_page_recommendations"]:
                st.markdown(f"- {rec}")

        # Conversion tracking
        with st.expander("📊 Conversion Tracking Setup", expanded=False):
            for item in package["conversion_tracking"]:
                st.markdown(f"- {item}")

        # Download button
        st.divider()
        json_bytes = json.dumps(package, indent=2).encode("utf-8")
        st.download_button(
            label="⬇️ Download Campaign Brief (JSON)",
            data=json_bytes,
            file_name=f"campaign_{sub_vertical}_{metro.lower().replace(' ', '_')}.json",
            mime="application/json",
        )

    # ======================================================================
    # Section 2 — Budget ROI Calculator
    # ======================================================================
    st.divider()
    st.subheader("💰 Budget ROI Calculator")

    roi_c1, roi_c2, roi_c3, roi_c4 = st.columns(4)
    roi_budget = roi_c1.number_input(
        "Monthly Budget ($)", min_value=100.0, value=3000.0, step=100.0, key="roi_budget"
    )
    roi_cpl = roi_c2.number_input(
        "Target CPL ($)", min_value=10.0, value=150.0, step=10.0, key="roi_cpl"
    )
    roi_close_rate = roi_c3.slider(
        "Close Rate (%)", min_value=1, max_value=50, value=15, key="roi_close"
    )
    roi_deal_value = roi_c4.number_input(
        "Avg Deal Value ($)", min_value=100.0, value=2500.0, step=100.0, key="roi_deal"
    )

    # Auto-calculate
    est_leads = roi_budget / roi_cpl if roi_cpl > 0 else 0
    est_clients = est_leads * (roi_close_rate / 100.0)
    est_revenue = est_clients * roi_deal_value
    roi_pct = ((est_revenue - roi_budget) / roi_budget * 100.0) if roi_budget > 0 else 0.0
    breakeven_leads = roi_budget / (roi_deal_value * (roi_close_rate / 100.0)) if (roi_deal_value * roi_close_rate) > 0 else 0.0

    rm1, rm2, rm3, rm4, rm5 = st.columns(5)
    rm1.metric("Est. Leads / Month", f"{est_leads:.0f}")
    rm2.metric("Est. New Clients", f"{est_clients:.1f}")
    rm3.metric("Est. Revenue", f"${est_revenue:,.0f}")
    rm4.metric("ROI %", f"{roi_pct:.0f}%", delta=f"{roi_pct - 100:.0f}%" if roi_pct != 100 else None)
    rm5.metric("Break-Even Leads", f"{breakeven_leads:.1f}")

    # ======================================================================
    # Section 3 — Keyword Planner
    # ======================================================================
    st.divider()
    st.subheader("🔑 Keyword Planner")

    all_sub_verticals = [sv for subs in _VERTICAL_OPTIONS.values() for sv in subs]
    kw_labels = [_SUB_VERTICAL_LABELS.get(s, s) for s in all_sub_verticals]
    kw_label_sel = st.selectbox("Sub-Vertical", options=kw_labels, key="kw_sub")
    kw_sub = all_sub_verticals[kw_labels.index(kw_label_sel)]

    keywords = TargetingConfig.KEYWORD_THEMES.get(kw_sub, [])
    base_cpc = _ESTIMATED_CPC.get(kw_sub, 30.0)

    kw_rows = []
    match_types = ["Exact", "Phrase", "Broad"]
    cpc_multipliers = [1.0, 0.85, 0.70]
    for kw in keywords:
        for mt, mult in zip(match_types, cpc_multipliers):
            kw_rows.append({
                "Keyword": kw,
                "Match Type": mt,
                "Estimated CPC ($)": round(base_cpc * mult, 2),
            })

    kw_df = pd.DataFrame(kw_rows)
    st.dataframe(kw_df, use_container_width=True, hide_index=True)

    csv_bytes = kw_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Keywords (CSV)",
        data=csv_bytes,
        file_name=f"keywords_{kw_sub}.csv",
        mime="text/csv",
        key="kw_download",
    )
