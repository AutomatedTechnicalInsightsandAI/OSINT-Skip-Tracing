"""
financials/financial_streamlit_tab.py
======================================
Renders the "💰 Financial Model" tab inside the main Streamlit app.

Call :func:`render_financial_tab` from ``app.py``, passing the current
leads DataFrame (may be empty — the tab works standalone).
"""

from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from financials.break_even import BreakEvenCalculator, DEFAULT_FIXED_COSTS
from financials.projections import RevenueProjections
from financials.unit_economics import VERTICAL_ECONOMICS, UnitEconomics


# ---------------------------------------------------------------------------
# Helper: tier badge
# ---------------------------------------------------------------------------

def _tier_badge(margin_pct: float) -> str:
    """Return an emoji tier label based on gross-margin percentage."""
    if margin_pct >= 0.70:
        return "🏆 S"
    if margin_pct >= 0.55:
        return "🥇 A"
    if margin_pct >= 0.40:
        return "🥈 B"
    return "🥉 C"


def _tier_color(margin_pct: float) -> str:
    if margin_pct >= 0.70:
        return "#00b300"
    if margin_pct >= 0.55:
        return "#66cc00"
    if margin_pct >= 0.40:
        return "#ffcc00"
    return "#ff6600"


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------


def render_financial_tab(df: pd.DataFrame) -> None:
    """
    Render the complete Financial Model tab.

    Parameters
    ----------
    df:
        The current leads DataFrame (may be empty). Only used in future
        integrations — the financial module works standalone.
    """
    ue = UnitEconomics()
    be = BreakEvenCalculator()
    rp = RevenueProjections()

    tabs = st.tabs(
        [
            "📊 Unit Economics",
            "⚖️ Break-Even Calculator",
            "📈 12-Month Projections",
            "🎯 Vertical Ranker",
        ]
    )

    # ======================================================================
    # TAB 1 — Unit Economics
    # ======================================================================
    with tabs[0]:
        st.subheader("Unit Economics by Vertical")

        vertical_options = list(VERTICAL_ECONOMICS.keys())
        selected_vertical = st.selectbox(
            "Select Vertical",
            options=vertical_options,
            format_func=lambda v: v.replace("_", " ").title(),
            key="ue_vertical",
        )

        ranked = ue.rank_sub_verticals_by_margin(selected_vertical)

        # --- Metric cards ---
        best = ranked[0]
        worst = ranked[-1]
        avg_margin = sum(r["gross_margin_pct"] for r in ranked) / len(ranked)

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Best Margin",
            f"{best['sub_vertical'].replace('_', ' ').title()}",
            f"{best['gross_margin_pct']:.1%}",
        )
        c2.metric(
            "Worst Margin",
            f"{worst['sub_vertical'].replace('_', ' ').title()}",
            f"{worst['gross_margin_pct']:.1%}",
        )
        c3.metric("Average Margin", f"{avg_margin:.1%}")

        st.divider()

        # --- Table ---
        table_data = []
        for r in ranked:
            ltv_cac = ue.calculate_ltv_to_cac(selected_vertical, r["sub_vertical"])
            table_data.append(
                {
                    "Sub-Vertical": r["sub_vertical"].replace("_", " ").title(),
                    "Lead Price ($)": r["lead_price"],
                    "CAC ($)": r["cac"],
                    "LTV ($)": r["ltv"],
                    "Close Rate": f"{r['close_rate']:.0%}",
                    "Gross Profit/Lead ($)": r["gross_profit_per_lead"],
                    "Gross Margin %": f"{r['gross_margin_pct']:.1%}",
                    "LTV:CAC": ltv_cac,
                    "Payback (mo)": r["payback_period_months"],
                    "Tier": _tier_badge(r["gross_margin_pct"]),
                }
            )

        table_df = pd.DataFrame(table_data)

        def _color_margin(val: str) -> str:
            try:
                pct = float(val.strip("%")) / 100
            except (ValueError, AttributeError):
                return ""
            color = _tier_color(pct)
            return f"color: {color}; font-weight: bold"

        styled = table_df.style.map(_color_margin, subset=["Gross Margin %"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.divider()

        # --- Bar chart: gross margin % ---
        bar_df = pd.DataFrame(
            {
                "Sub-Vertical": [r["sub_vertical"].replace("_", " ").title() for r in ranked],
                "Gross Margin %": [r["gross_margin_pct"] * 100 for r in ranked],
            }
        )
        fig_bar = px.bar(
            bar_df,
            x="Sub-Vertical",
            y="Gross Margin %",
            title=f"Gross Margin % — {selected_vertical.replace('_', ' ').title()}",
            color="Gross Margin %",
            color_continuous_scale="RdYlGn",
            text_auto=".1f",
        )
        fig_bar.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

        # --- Scatter: LTV vs CAC across all verticals ---
        st.subheader("LTV vs CAC — All Verticals")
        scatter_rows = []
        for v, sv_dict in VERTICAL_ECONOMICS.items():
            for sv, data in sv_dict.items():
                scatter_rows.append(
                    {
                        "Sub-Vertical": sv.replace("_", " ").title(),
                        "Vertical": v.replace("_", " ").title(),
                        "LTV ($)": data["ltv"],
                        "CAC ($)": data["cac"],
                        "Lead Price ($)": data["lead_price"],
                    }
                )
        scatter_df = pd.DataFrame(scatter_rows)
        fig_scatter = px.scatter(
            scatter_df,
            x="CAC ($)",
            y="LTV ($)",
            color="Vertical",
            hover_name="Sub-Vertical",
            size="Lead Price ($)",
            title="LTV vs CAC (bubble size = lead price)",
            log_y=True,
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    # ======================================================================
    # TAB 2 — Break-Even Calculator
    # ======================================================================
    with tabs[1]:
        st.subheader("Platform Break-Even Calculator")

        # --- Fixed costs ---
        with st.expander("⚙️ Monthly Fixed Costs", expanded=True):
            fc_col1, fc_col2 = st.columns(2)
            attom = fc_col1.number_input("ATTOM API ($)", value=DEFAULT_FIXED_COSTS["attom_api"], min_value=0.0, step=10.0, key="fc_attom")
            bubble = fc_col1.number_input("Bubble.io ($)", value=DEFAULT_FIXED_COSTS["bubble_io"], min_value=0.0, step=10.0, key="fc_bubble")
            gmaps = fc_col2.number_input("Google Maps ($)", value=DEFAULT_FIXED_COSTS["google_maps"], min_value=0.0, step=10.0, key="fc_gmaps")
            other = fc_col2.number_input("Other ($)", value=DEFAULT_FIXED_COSTS["other"], min_value=0.0, step=10.0, key="fc_other")

        fixed_costs = {"attom_api": attom, "bubble_io": bubble, "google_maps": gmaps, "other": other}

        # --- Lead volume sliders ---
        st.subheader("Lead Volume Mix (per month)")
        lead_mix: list[dict] = []
        slider_cols = st.columns(3)

        vert_list = [
            ("home_services", "hvac"),
            ("home_services", "roofing"),
            ("home_services", "solar"),
            ("real_estate",   "dscr_loan"),
            ("real_estate",   "hard_money"),
            ("real_estate",   "commercial_re"),
            ("b2b",           "smb"),
            ("b2b",           "mid_market"),
            ("b2b",           "enterprise"),
        ]

        for i, (vert, sv) in enumerate(vert_list):
            col = slider_cols[i % 3]
            label = f"{sv.replace('_', ' ').title()} ({vert.replace('_', ' ').title()})"
            vol = col.slider(label, min_value=0, max_value=100, value=5, step=1, key=f"vol_{vert}_{sv}")
            if vol > 0:
                lead_mix.append({"vertical": vert, "sub_vertical": sv, "volume": vol})

        be_result = be.calculate_platform_breakeven(
            monthly_fixed_costs=fixed_costs,
            lead_mix=lead_mix if lead_mix else None,
        )

        st.divider()
        st.subheader("Platform Break-Even Results")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Revenue", f"${be_result['total_revenue']:,.2f}")
        m2.metric("Total Costs", f"${be_result['total_fixed_costs'] + be_result['total_variable_costs']:,.2f}")
        m3.metric("Gross Profit", f"${be_result['gross_profit']:,.2f}")
        m4.metric("Gross Margin", f"{be_result['gross_margin_pct']:.1%}")

        m5, m6, m7 = st.columns(3)
        m5.metric("Break-Even Leads", f"{be_result['break_even_leads']:,}")
        m6.metric("Break-Even Revenue", f"${be_result['break_even_revenue']:,.2f}")
        profit_loss = be_result["current_profit_loss"]
        m7.metric(
            "Current P&L",
            f"${profit_loss:,.2f}",
            delta=f"{'▲' if profit_loss >= 0 else '▼'} {'Profitable' if profit_loss >= 0 else 'Loss'}",
        )

        # --- Waterfall chart ---
        wf_fig = go.Figure(
            go.Waterfall(
                name="P&L",
                orientation="v",
                measure=["absolute", "relative", "relative", "total"],
                x=["Revenue", "Variable Costs", "Fixed Costs", "Net P&L"],
                y=[
                    be_result["total_revenue"],
                    -be_result["total_variable_costs"],
                    -be_result["total_fixed_costs"],
                    be_result["current_profit_loss"],
                ],
                connector={"line": {"color": "rgb(63,63,63)"}},
            )
        )
        wf_fig.update_layout(title="Monthly P&L Waterfall", showlegend=False)
        st.plotly_chart(wf_fig, use_container_width=True)

        st.divider()

        # --- Buyer ROI Calculator ---
        st.subheader("🧮 Buyer ROI Calculator")
        st.caption("From the buyer's perspective — how many leads do they need to break even?")

        b1, b2 = st.columns(2)
        buyer_lead_price = b1.number_input("Lead Price ($)", value=350.0, min_value=1.0, step=10.0, key="buyer_lp")
        buyer_close_rate = b1.slider("Close Rate", min_value=0.01, max_value=1.0, value=0.20, step=0.01, key="buyer_cr")
        buyer_avg_deal = b2.number_input("Avg Deal Value ($)", value=1_000_000.0, min_value=1.0, step=10000.0, key="buyer_deal")
        buyer_orig_pct = b2.slider("Origination %", min_value=0.0, max_value=0.10, value=0.015, step=0.001, format="%.3f", key="buyer_orig")

        buyer_result = be.calculate_buyer_breakeven(
            lead_price=buyer_lead_price,
            close_rate=buyer_close_rate,
            avg_deal_value=buyer_avg_deal,
            origination_pct=buyer_orig_pct,
        )

        bm1, bm2, bm3, bm4 = st.columns(4)
        bm1.metric("Revenue / Closed Lead", f"${buyer_result['revenue_per_closed_lead']:,.2f}")
        bm2.metric("Cost / Closed Lead", f"${buyer_result['cost_per_closed_lead']:,.2f}")
        bm3.metric("ROI per Lead", f"{buyer_result['roi_per_lead']:.1%}")
        bm4.metric("Payback Period", f"{buyer_result['payback_period_days']} days")

        bm5, bm6 = st.columns(2)
        bm5.metric("Leads to Break Even", f"{buyer_result['leads_to_break_even']:,}")
        bm6.metric("Monthly Investment", f"${buyer_result['monthly_investment']:,.2f}")

        # --- Sensitivity chart ---
        with st.expander("📉 Sensitivity Analysis — Vary Close Rate"):
            sens = be.sensitivity_analysis(
                base_scenario={
                    "lead_price": buyer_lead_price,
                    "close_rate": buyer_close_rate,
                    "avg_deal_value": buyer_avg_deal,
                    "origination_pct": buyer_orig_pct,
                },
                variable="close_rate",
                range_pct=0.30,
            )
            sens_df = pd.DataFrame(sens)
            if not sens_df.empty:
                fig_sens = px.line(
                    sens_df,
                    x="close_rate",
                    y="current_profit_loss",
                    title="P&L per Lead vs Close Rate (±30%)",
                    labels={"close_rate": "Close Rate", "current_profit_loss": "P&L per Lead ($)"},
                    markers=True,
                )
                fig_sens.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break-even")
                st.plotly_chart(fig_sens, use_container_width=True)

    # ======================================================================
    # TAB 3 — 12-Month Projections
    # ======================================================================
    with tabs[2]:
        st.subheader("12-Month Revenue Projections")

        p1, p2 = st.columns(2)
        init_buyers = p1.number_input("Initial Buyers", value=10, min_value=1, step=1, key="proj_init")
        growth_rate = p1.slider("Monthly Growth Rate", 0.05, 0.50, 0.15, 0.01, key="proj_growth")
        avg_spend = p2.number_input("Avg Spend / Buyer ($)", value=1200.0, min_value=100.0, step=100.0, key="proj_spend")
        churn = p2.slider("Monthly Churn Rate", 0.01, 0.30, 0.05, 0.01, key="proj_churn")

        if st.button("▶ Run Projection", type="primary", key="proj_run"):
            st.session_state["proj_df_base"] = rp.build_12_month_projection(
                initial_buyers=init_buyers,
                monthly_buyer_growth_rate=growth_rate,
                avg_spend_per_buyer=avg_spend,
                churn_rate=churn,
            )
        elif "proj_df_base" not in st.session_state:
            st.session_state["proj_df_base"] = rp.build_12_month_projection(
                initial_buyers=init_buyers,
                monthly_buyer_growth_rate=growth_rate,
                avg_spend_per_buyer=avg_spend,
                churn_rate=churn,
            )

        base_df: pd.DataFrame = st.session_state["proj_df_base"]

        # Three scenarios
        scenarios_data = [
            {"name": "Conservative", "monthly_buyer_growth_rate": 0.10,
             "initial_buyers": init_buyers, "avg_spend_per_buyer": avg_spend, "churn_rate": churn},
            {"name": "Base",         "monthly_buyer_growth_rate": growth_rate,
             "initial_buyers": init_buyers, "avg_spend_per_buyer": avg_spend, "churn_rate": churn},
            {"name": "Aggressive",   "monthly_buyer_growth_rate": 0.25,
             "initial_buyers": init_buyers, "avg_spend_per_buyer": avg_spend, "churn_rate": churn},
        ]

        scenario_dfs: dict[str, pd.DataFrame] = {}
        for sc in scenarios_data:
            name = sc["name"]
            kwargs = {k: v for k, v in sc.items() if k != "name"}
            scenario_dfs[name] = rp.build_12_month_projection(**kwargs)

        # --- Metrics ---
        summary = rp.calculate_metrics_summary(base_df)
        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("12M Total Revenue", f"${summary['total_12m_revenue']:,.0f}")
        sm2.metric("Peak MRR", f"${summary['peak_mrr']:,.0f}")
        sm3.metric("Break-Even Month", f"Month {summary['break_even_month']}" if summary["break_even_month"] > 0 else "Not reached")
        sm4.metric("12M Net Profit", f"${summary['total_12m_profit']:,.0f}")

        st.divider()

        # --- MRR line chart (all 3 scenarios) ---
        mrr_combined = pd.DataFrame({"Month": range(1, 13)})
        for name, sdf in scenario_dfs.items():
            mrr_combined[name] = sdf["MRR"].values

        fig_mrr = px.line(
            mrr_combined.melt(id_vars="Month", var_name="Scenario", value_name="MRR ($)"),
            x="Month",
            y="MRR ($)",
            color="Scenario",
            title="Monthly Recurring Revenue — 3 Scenarios",
            markers=True,
        )
        st.plotly_chart(fig_mrr, use_container_width=True)

        # --- Net profit bar chart ---
        fig_profit = px.bar(
            base_df,
            x="Month",
            y="Net_Profit",
            title="Monthly Net Profit (Base Scenario)",
            color="Net_Profit",
            color_continuous_scale="RdYlGn",
            labels={"Net_Profit": "Net Profit ($)"},
        )
        fig_profit.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_profit, use_container_width=True)

        # --- Full projection table ---
        with st.expander("📋 Full 12-Month Projection Table"):
            st.dataframe(base_df, use_container_width=True, hide_index=True)

        # --- Download ---
        csv_buf = io.StringIO()
        base_df.to_csv(csv_buf, index=False)
        st.download_button(
            "⬇️ Export Projections (CSV)",
            data=csv_buf.getvalue().encode("utf-8"),
            file_name="12_month_projection.csv",
            mime="text/csv",
        )

    # ======================================================================
    # TAB 4 — Vertical Ranker
    # ======================================================================
    with tabs[3]:
        st.subheader("🎯 Top Sub-Vertical Ranker")
        st.caption("Ranked by gross margin % across all verticals")

        top_n = st.slider("Show top N sub-verticals", min_value=5, max_value=17, value=10, key="ranker_n")
        top = ue.get_top_verticals(n=top_n)

        ranker_rows = []
        for rank, row in enumerate(top, start=1):
            ltv_cac = ue.calculate_ltv_to_cac(row["vertical"], row["sub_vertical"])
            ranker_rows.append(
                {
                    "Rank": rank,
                    "Sub-Vertical": row["sub_vertical"].replace("_", " ").title(),
                    "Vertical": row["vertical"].replace("_", " ").title(),
                    "Lead Price ($)": row["lead_price"],
                    "CAC ($)": row["cac"],
                    "LTV ($)": row["ltv"],
                    "Gross Margin %": f"{row['gross_margin_pct']:.1%}",
                    "LTV:CAC": ltv_cac,
                    "Tier": _tier_badge(row["gross_margin_pct"]),
                }
            )

        ranker_df = pd.DataFrame(ranker_rows)

        def _color_tier(val: str) -> str:
            colors = {
                "🏆 S": "background-color: #004d00; color: white",
                "🥇 A": "background-color: #1a6600; color: white",
                "🥈 B": "background-color: #666600; color: white",
                "🥉 C": "background-color: #4d2600; color: white",
            }
            return colors.get(val, "")

        styled_ranker = ranker_df.style.map(_color_tier, subset=["Tier"])
        st.dataframe(styled_ranker, use_container_width=True, hide_index=True)

        # --- Horizontal bar chart ---
        rank_chart_df = pd.DataFrame(
            {
                "Sub-Vertical": [r["sub_vertical"].replace("_", " ").title() for r in top],
                "Gross Margin %": [r["gross_margin_pct"] * 100 for r in top],
                "Vertical": [r["vertical"].replace("_", " ").title() for r in top],
            }
        ).sort_values("Gross Margin %", ascending=True)

        fig_rank = px.bar(
            rank_chart_df,
            x="Gross Margin %",
            y="Sub-Vertical",
            orientation="h",
            color="Vertical",
            title=f"Top {top_n} Sub-Verticals by Gross Margin",
            text_auto=".1f",
        )
        st.plotly_chart(fig_rank, use_container_width=True)

        # --- Download ---
        csv_buf2 = io.StringIO()
        ranker_df.to_csv(csv_buf2, index=False)
        st.download_button(
            "⬇️ Export Ranking (CSV)",
            data=csv_buf2.getvalue().encode("utf-8"),
            file_name="vertical_ranking.csv",
            mime="text/csv",
            key="ranker_download",
        )
