"""
financials/break_even.py
=========================
Break-even analysis for both the **platform** (us) and the **buyer**
(the lead purchaser).
"""

from __future__ import annotations

import math
from typing import Any

from financials.unit_economics import VERTICAL_ECONOMICS, UnitEconomics

# Default fixed costs when none are supplied by the caller
DEFAULT_FIXED_COSTS: dict[str, float] = {
    "attom_api":  299.0,
    "bubble_io":  119.0,
    "google_maps": 50.0,
    "other":      100.0,
}


class BreakEvenCalculator:
    """
    Break-even and ROI calculations from two perspectives:

    1. **Platform** — how many leads do *we* need to sell to cover costs?
    2. **Buyer**    — how many leads does *the buyer* need to purchase to
                      recoup their investment?
    """

    def __init__(self) -> None:
        self._ue = UnitEconomics()

    # ------------------------------------------------------------------
    # Platform break-even
    # ------------------------------------------------------------------

    def calculate_platform_breakeven(
        self,
        monthly_fixed_costs: dict[str, float] | None = None,
        lead_mix: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Calculate platform-level break-even given fixed costs and a
        proposed lead volume mix.

        Parameters
        ----------
        monthly_fixed_costs:
            Dict of cost-name → monthly amount (USD).
            Defaults to ``DEFAULT_FIXED_COSTS``.
        lead_mix:
            List of dicts, each with keys ``vertical`` (str),
            ``sub_vertical`` (str), and ``volume`` (int).
            Defaults to a minimal illustrative mix if omitted.

        Returns
        -------
        dict with keys:
            ``total_fixed_costs``, ``total_variable_costs``,
            ``total_revenue``, ``gross_profit``, ``gross_margin_pct``,
            ``break_even_leads``, ``break_even_revenue``,
            ``current_profit_loss``, ``months_to_profitability``,
            ``per_vertical_breakdown``
        """
        if monthly_fixed_costs is None:
            monthly_fixed_costs = DEFAULT_FIXED_COSTS.copy()

        if lead_mix is None:
            lead_mix = [
                {"vertical": "home_services", "sub_vertical": "hvac",       "volume": 10},
                {"vertical": "real_estate",   "sub_vertical": "dscr_loan",  "volume": 5},
                {"vertical": "b2b",           "sub_vertical": "smb",        "volume": 5},
            ]

        total_fixed = sum(monthly_fixed_costs.values())
        total_revenue = 0.0
        total_variable = 0.0
        per_vertical: dict[str, dict[str, Any]] = {}

        for entry in lead_mix:
            vertical = entry["vertical"]
            sv = entry["sub_vertical"]
            volume = int(entry.get("volume", 0))
            if volume <= 0:
                continue

            data = VERTICAL_ECONOMICS[vertical][sv]
            lead_price: float = data["lead_price"]
            cac: float = data["cac"]

            revenue = lead_price * volume
            variable_cost = cac * volume
            gross = revenue - variable_cost

            total_revenue += revenue
            total_variable += variable_cost

            key = f"{vertical}/{sv}"
            per_vertical[key] = {
                "volume": volume,
                "lead_price": lead_price,
                "cac": cac,
                "revenue": round(revenue, 2),
                "variable_cost": round(variable_cost, 2),
                "gross_profit": round(gross, 2),
                "gross_margin_pct": round((gross / revenue) if revenue else 0.0, 4),
            }

        gross_profit = total_revenue - total_variable
        gross_margin_pct = (gross_profit / total_revenue) if total_revenue else 0.0

        # Average gross profit per lead across the mix
        total_volume = sum(int(e.get("volume", 0)) for e in lead_mix)
        avg_gross_per_lead = (gross_profit / total_volume) if total_volume else 0.0

        # Leads needed to cover fixed costs (variable costs already deducted)
        if avg_gross_per_lead > 0:
            break_even_leads = math.ceil(total_fixed / avg_gross_per_lead)
        else:
            break_even_leads = 0

        # Average lead price across the mix
        avg_lead_price = (total_revenue / total_volume) if total_volume else 0.0
        break_even_revenue = break_even_leads * avg_lead_price

        current_profit_loss = gross_profit - total_fixed

        # If already profitable, 0 months; otherwise estimate ramp months
        if current_profit_loss >= 0:
            months_to_profitability = 0
        elif gross_profit > 0:
            months_to_profitability = math.ceil(total_fixed / gross_profit)
        else:
            months_to_profitability = -1  # cannot reach profitability with current mix

        return {
            "total_fixed_costs": round(total_fixed, 2),
            "total_variable_costs": round(total_variable, 2),
            "total_revenue": round(total_revenue, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_margin_pct": round(gross_margin_pct, 4),
            "break_even_leads": break_even_leads,
            "break_even_revenue": round(break_even_revenue, 2),
            "current_profit_loss": round(current_profit_loss, 2),
            "months_to_profitability": months_to_profitability,
            "per_vertical_breakdown": per_vertical,
        }

    # ------------------------------------------------------------------
    # Buyer break-even
    # ------------------------------------------------------------------

    def calculate_buyer_breakeven(
        self,
        lead_price: float,
        close_rate: float,
        avg_deal_value: float,
        origination_pct: float = 0.0,
    ) -> dict[str, Any]:
        """
        Return break-even metrics from the **buyer's** perspective.

        Parameters
        ----------
        lead_price:
            Price paid per lead (USD).
        close_rate:
            Fraction of leads that convert to closed deals (0–1).
        avg_deal_value:
            Average deal value in USD (loan amount, contract value, etc.).
        origination_pct:
            Origination / commission percentage of deal value (0–1).
            Use 0 for non-origination verticals.

        Returns
        -------
        dict with keys:
            ``revenue_per_closed_lead``, ``cost_per_closed_lead``,
            ``roi_per_lead``, ``leads_to_break_even``,
            ``monthly_investment``, ``monthly_revenue_at_break_even``,
            ``payback_period_days``
        """
        if close_rate <= 0:
            raise ValueError("close_rate must be greater than 0")
        if lead_price < 0:
            raise ValueError("lead_price must be non-negative")

        # Revenue earned per lead purchased (expected value)
        if origination_pct > 0:
            revenue_per_closed = avg_deal_value * origination_pct
        else:
            revenue_per_closed = avg_deal_value

        revenue_per_lead_purchased = close_rate * revenue_per_closed

        # Cost to generate one closed deal
        cost_per_closed = lead_price / close_rate

        roi_per_lead = (revenue_per_lead_purchased - lead_price) / lead_price if lead_price else 0.0

        # Leads needed so that total revenue ≥ total cost
        if revenue_per_lead_purchased > lead_price:
            leads_to_break_even = 1  # first lead is already profitable
        elif revenue_per_lead_purchased > 0:
            leads_to_break_even = math.ceil(lead_price / revenue_per_lead_purchased)
        else:
            leads_to_break_even = 0  # undefined / cannot break even

        monthly_investment = lead_price * leads_to_break_even
        monthly_revenue_at_break_even = revenue_per_lead_purchased * leads_to_break_even

        # Rough payback: assume 30-day month, linear close cadence
        avg_days_per_close = 30.0 / close_rate if close_rate else float("inf")
        payback_period_days = math.ceil(avg_days_per_close) if avg_days_per_close != float("inf") else 0

        return {
            "revenue_per_closed_lead": round(revenue_per_closed, 2),
            "cost_per_closed_lead": round(cost_per_closed, 2),
            "roi_per_lead": round(roi_per_lead, 4),
            "leads_to_break_even": leads_to_break_even,
            "monthly_investment": round(monthly_investment, 2),
            "monthly_revenue_at_break_even": round(monthly_revenue_at_break_even, 2),
            "payback_period_days": payback_period_days,
        }

    # ------------------------------------------------------------------
    # Sensitivity analysis
    # ------------------------------------------------------------------

    def sensitivity_analysis(
        self,
        base_scenario: dict[str, Any],
        variable: str,
        range_pct: float = 0.30,
    ) -> list[dict[str, Any]]:
        """
        Vary *variable* in *base_scenario* by ±*range_pct* in 10 equal
        steps and return a scenario list.

        Parameters
        ----------
        base_scenario:
            Dict with keys accepted by :meth:`calculate_buyer_breakeven`:
            ``lead_price``, ``close_rate``, ``avg_deal_value``,
            ``origination_pct``.
        variable:
            One of ``"close_rate"``, ``"lead_price"``, or ``"avg_deal_value"``.
        range_pct:
            Fractional range for the sweep (default ±30 %).

        Returns
        -------
        List of dicts, each containing the varied ``variable`` value,
        the computed ``roi_per_lead``, and ``current_profit_loss``
        (revenue − cost per lead purchased).
        """
        if variable not in ("close_rate", "lead_price", "avg_deal_value"):
            raise ValueError(
                f"variable must be one of 'close_rate', 'lead_price', "
                f"'avg_deal_value'; got '{variable}'"
            )

        base_value: float = base_scenario[variable]
        steps = 10
        results: list[dict[str, Any]] = []

        for i in range(steps + 1):
            factor = (1.0 - range_pct) + (2.0 * range_pct * i / steps)
            varied_value = base_value * factor

            scenario = dict(base_scenario)
            scenario[variable] = varied_value

            # close_rate must stay in (0, 1]
            if scenario["close_rate"] <= 0:
                continue

            metrics = self.calculate_buyer_breakeven(
                lead_price=scenario["lead_price"],
                close_rate=scenario["close_rate"],
                avg_deal_value=scenario["avg_deal_value"],
                origination_pct=scenario.get("origination_pct", 0.0),
            )

            close_r = scenario["close_rate"]
            orig = scenario.get("origination_pct", 0.0)
            avg_deal = scenario["avg_deal_value"]
            lp = scenario["lead_price"]
            rev_per_lead = close_r * (avg_deal * orig if orig > 0 else avg_deal)
            profit_per_lead = rev_per_lead - lp

            results.append(
                {
                    variable: round(varied_value, 6),
                    "roi_per_lead": metrics["roi_per_lead"],
                    "current_profit_loss": round(profit_per_lead, 2),
                    "leads_to_break_even": metrics["leads_to_break_even"],
                    "payback_period_days": metrics["payback_period_days"],
                }
            )

        return results
