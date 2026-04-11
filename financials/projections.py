"""
financials/projections.py
==========================
12-month revenue projections and scenario comparisons.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


class RevenueProjections:
    """
    Builds forward-looking revenue models for the platform.

    Key assumptions (all overridable via method parameters):

    - COGS:  12 % of revenue (API costs, infrastructure)
    - OpEx:  $2 000 / month fixed  +  8 % of revenue variable
    """

    # Fixed assumptions exposed as class attributes so they are visible
    # in tests and docs without digging through method bodies.
    COGS_PCT: float = 0.12       # fraction of revenue
    OPEX_FIXED: float = 2000.0   # USD / month
    OPEX_VARIABLE_PCT: float = 0.08  # fraction of revenue

    # ------------------------------------------------------------------
    # 12-month projection
    # ------------------------------------------------------------------

    def build_12_month_projection(
        self,
        initial_buyers: int = 10,
        monthly_buyer_growth_rate: float = 0.15,
        avg_spend_per_buyer: float = 1200.0,
        churn_rate: float = 0.05,
        vertical_mix: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """
        Build a 12-month revenue projection DataFrame.

        Parameters
        ----------
        initial_buyers:
            Number of paying buyers at the start of month 1.
        monthly_buyer_growth_rate:
            Fraction of *current active buyers* added as new buyers each month.
        avg_spend_per_buyer:
            Average monthly spend per active buyer (USD).
        churn_rate:
            Fraction of active buyers lost each month.
        vertical_mix:
            Optional dict mapping vertical name → fraction of revenue.
            Not used in calculations but stored for reference.

        Returns
        -------
        pd.DataFrame with columns:
            Month, New_Buyers, Churned_Buyers, Active_Buyers,
            Leads_Delivered, Gross_Revenue, COGS, Gross_Profit,
            Operating_Expenses, Net_Profit, Cumulative_Revenue, MRR
        """
        rows: list[dict[str, Any]] = []
        active_buyers = float(initial_buyers)
        cumulative_revenue = 0.0

        for month in range(1, 13):
            new_buyers = math.ceil(active_buyers * monthly_buyer_growth_rate)
            churned = math.floor(active_buyers * churn_rate)
            active_buyers = active_buyers + new_buyers - churned
            if active_buyers < 0:
                active_buyers = 0.0

            mrr = active_buyers * avg_spend_per_buyer
            gross_revenue = mrr

            cogs = gross_revenue * self.COGS_PCT
            gross_profit = gross_revenue - cogs

            opex = self.OPEX_FIXED + gross_revenue * self.OPEX_VARIABLE_PCT
            net_profit = gross_profit - opex

            cumulative_revenue += gross_revenue

            # Approximate leads delivered (avg $185 per lead as proxy)
            avg_lead_price = 185.0
            leads_delivered = int(gross_revenue / avg_lead_price)

            rows.append(
                {
                    "Month": month,
                    "New_Buyers": new_buyers,
                    "Churned_Buyers": churned,
                    "Active_Buyers": round(active_buyers, 2),
                    "Leads_Delivered": leads_delivered,
                    "Gross_Revenue": round(gross_revenue, 2),
                    "COGS": round(cogs, 2),
                    "Gross_Profit": round(gross_profit, 2),
                    "Operating_Expenses": round(opex, 2),
                    "Net_Profit": round(net_profit, 2),
                    "Cumulative_Revenue": round(cumulative_revenue, 2),
                    "MRR": round(mrr, 2),
                }
            )

        df = pd.DataFrame(rows)
        # Ensure correct dtypes
        int_cols = ["Month", "New_Buyers", "Churned_Buyers", "Leads_Delivered"]
        for col in int_cols:
            df[col] = df[col].astype(int)
        float_cols = [
            c for c in df.columns if c not in int_cols
        ]
        for col in float_cols:
            df[col] = df[col].astype(float).round(2)

        return df

    # ------------------------------------------------------------------
    # Metrics summary
    # ------------------------------------------------------------------

    def calculate_metrics_summary(self, projections_df: pd.DataFrame) -> dict[str, Any]:
        """
        Summarise a 12-month projection DataFrame.

        Parameters
        ----------
        projections_df:
            DataFrame as returned by :meth:`build_12_month_projection`.

        Returns
        -------
        dict with keys:
            ``total_12m_revenue``, ``total_12m_profit``, ``peak_mrr``,
            ``avg_gross_margin``, ``ltv_per_buyer``, ``cac_blended``,
            ``ltv_to_cac_ratio``, ``break_even_month``
        """
        total_revenue = float(projections_df["Gross_Revenue"].sum())
        total_profit = float(projections_df["Net_Profit"].sum())
        peak_mrr = float(projections_df["MRR"].max())

        gross_margins = (
            (projections_df["Gross_Profit"] / projections_df["Gross_Revenue"])
            .replace([float("inf"), float("nan")], 0.0)
        )
        avg_gross_margin = float(gross_margins.mean())

        # Blended LTV: assume avg buyer stays 12 months, paying avg spend
        # Use the last row's active buyers and MRR for a rough estimate
        last_row = projections_df.iloc[-1]
        avg_mrr_per_buyer = (
            last_row["MRR"] / last_row["Active_Buyers"]
            if last_row["Active_Buyers"] > 0
            else 0.0
        )
        ltv_per_buyer = avg_mrr_per_buyer * 12  # simplified 12-month LTV

        # Blended CAC: total opex / total new buyers acquired
        total_new_buyers = int(projections_df["New_Buyers"].sum())
        total_opex = float(projections_df["Operating_Expenses"].sum())
        cac_blended = total_opex / total_new_buyers if total_new_buyers else 0.0

        ltv_to_cac_ratio = ltv_per_buyer / cac_blended if cac_blended else float("inf")

        # Break-even month: first month with cumulative Net_Profit ≥ 0
        cum_net = projections_df["Net_Profit"].cumsum()
        profitable_months = projections_df.loc[cum_net >= 0, "Month"]
        break_even_month = int(profitable_months.iloc[0]) if not profitable_months.empty else -1

        return {
            "total_12m_revenue": round(total_revenue, 2),
            "total_12m_profit": round(total_profit, 2),
            "peak_mrr": round(peak_mrr, 2),
            "avg_gross_margin": round(avg_gross_margin, 4),
            "ltv_per_buyer": round(ltv_per_buyer, 2),
            "cac_blended": round(cac_blended, 2),
            "ltv_to_cac_ratio": round(ltv_to_cac_ratio, 2),
            "break_even_month": break_even_month,
        }

    # ------------------------------------------------------------------
    # Scenario comparison
    # ------------------------------------------------------------------

    def build_scenario_comparison(
        self,
        scenarios: list[dict[str, Any]] | None = None,
    ) -> pd.DataFrame:
        """
        Build a side-by-side scenario comparison DataFrame.

        If *scenarios* is omitted the three standard scenarios are used:

        - **Conservative** — 10 % monthly buyer growth
        - **Base**         — 15 % monthly buyer growth
        - **Aggressive**   — 25 % monthly buyer growth

        Parameters
        ----------
        scenarios:
            List of dicts, each with keys:
            ``name`` (str), and any kwargs accepted by
            :meth:`build_12_month_projection`.

        Returns
        -------
        pd.DataFrame with one row per scenario containing key metrics
        from :meth:`calculate_metrics_summary`.
        """
        if scenarios is None:
            scenarios = [
                {"name": "Conservative", "monthly_buyer_growth_rate": 0.10},
                {"name": "Base",         "monthly_buyer_growth_rate": 0.15},
                {"name": "Aggressive",   "monthly_buyer_growth_rate": 0.25},
            ]

        rows: list[dict[str, Any]] = []
        for scenario in scenarios:
            name = scenario.pop("name", "Unnamed")
            proj = self.build_12_month_projection(**scenario)
            summary = self.calculate_metrics_summary(proj)
            rows.append({"scenario": name, **summary})
            # Restore the name key so the original dict is not mutated
            scenario["name"] = name

        df = pd.DataFrame(rows)
        return df
