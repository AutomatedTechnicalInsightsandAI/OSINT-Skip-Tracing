"""
GoHighLevel Streamlit Tab
==========================

Provides a :func:`render_ghl_tab` function that renders a "Push to GHL"
Streamlit tab inside the existing dashboard.

Usage in app.py::

    from ghl.ghl_streamlit_tab import render_ghl_tab

    tab1, tab2 = st.tabs(["📋 Results", "📤 Push to GHL"])
    with tab2:
        render_ghl_tab(df)
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from ghl.lead_router import DeliveryResult, LeadRouter

logger = logging.getLogger(__name__)

_VERTICALS = {
    "Real Estate / Mortgage": "real_estate",
    "Home Services":          "home_services",
    "B2B":                    "b2b",
}


def render_ghl_tab(df: pd.DataFrame) -> None:
    """Render the 'Push to GoHighLevel' Streamlit tab.

    Parameters
    ----------
    df:
        DataFrame of scraped leads produced by the main scraper workflow.
        An empty DataFrame results in an info message and early return.
    """
    st.subheader("📤 Push to GoHighLevel")

    if df.empty:
        st.info(
            "No leads to push. Run **🚀 Generate Leads** on the Results tab first."
        )
        return

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    col_v, col_info = st.columns([1, 2])

    with col_v:
        vertical_label = st.selectbox(
            "Target Vertical",
            options=list(_VERTICALS.keys()),
            help="Choose which GHL pipeline to deliver leads into.",
        )

    vertical = _VERTICALS[vertical_label]

    with col_info:
        st.markdown(
            f"**{len(df)}** lead(s) ready to push into the "
            f"**{vertical_label}** pipeline."
        )

    st.divider()

    # ------------------------------------------------------------------
    # Push button
    # ------------------------------------------------------------------
    push_clicked = st.button(
        "🚀 Push All to GHL",
        type="primary",
        use_container_width=False,
        key="push_to_ghl",
    )

    if not push_clicked:
        return

    router = LeadRouter()
    results: list[DeliveryResult] = []
    pushed_at_timestamps: list[str] = []
    progress = st.progress(0, text="Pushing leads to GoHighLevel…")
    status_container = st.empty()
    rows: list[dict] = df.to_dict(orient="records")
    total = len(rows)

    for idx, row in enumerate(rows):
        lead_label = str(row.get("Owner Name", f"Lead #{idx + 1}"))
        status_container.markdown(f"⏳ Processing **{lead_label}**…")

        result = router.route(row, vertical=vertical)
        pushed_at_timestamps.append(datetime.now(timezone.utc).isoformat())
        results.append(result)

        icon = "✅" if result.success else "❌"
        logger.info(
            "GHL push %s/%s | %s success=%s error=%s",
            idx + 1,
            total,
            lead_label,
            result.success,
            result.error,
        )

        progress.progress(
            (idx + 1) / total,
            text=f"{icon} {idx + 1}/{total} — {lead_label}",
        )

    progress.empty()
    status_container.empty()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Pushed", total)
    m2.metric("✅ Succeeded", len(successes))
    m3.metric("❌ Failed", len(failures))

    if failures:
        st.warning("Some leads failed to push. See details below.")
        with st.expander("❌ Failure Details", expanded=True):
            for i, r in enumerate(failures, 1):
                st.markdown(f"**{i}.** `{r.error}`")

    # ------------------------------------------------------------------
    # Push report download
    # ------------------------------------------------------------------
    st.divider()
    report_rows = []
    for row, result, pushed_at in zip(rows, results, pushed_at_timestamps):
        report_rows.append(
            {
                "Owner Name":      row.get("Owner Name", ""),
                "Property Address": row.get("Property Address", ""),
                "County":          row.get("County", ""),
                "Vertical":        vertical_label,
                "Contact ID":      result.contact_id,
                "Opportunity ID":  result.opportunity_id,
                "Pipeline":        result.pipeline,
                "Stage":           result.stage,
                "Tags":            ", ".join(result.tags_applied),
                "Success":         result.success,
                "Error":           result.error or "",
                "Pushed At":       pushed_at,
            }
        )

    report_df = pd.DataFrame(report_rows)
    csv_buffer = io.StringIO()
    report_df.to_csv(csv_buffer, index=False)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    st.download_button(
        label="⬇️ Download Push Report",
        data=csv_bytes,
        file_name="ghl_push_report.csv",
        mime="text/csv",
        key="download_ghl_report",
    )
