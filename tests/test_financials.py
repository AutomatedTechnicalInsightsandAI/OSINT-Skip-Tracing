"""
tests/test_financials.py
=========================
Unit tests for the financials package.

Run with:
    pytest tests/test_financials.py -v
"""

from __future__ import annotations

import pytest
import pandas as pd

from financials.unit_economics import UnitEconomics, VERTICAL_ECONOMICS
from financials.break_even import BreakEvenCalculator, DEFAULT_FIXED_COSTS
from financials.projections import RevenueProjections


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ue() -> UnitEconomics:
    return UnitEconomics()


@pytest.fixture
def be() -> BreakEvenCalculator:
    return BreakEvenCalculator()


@pytest.fixture
def rp() -> RevenueProjections:
    return RevenueProjections()


# ---------------------------------------------------------------------------
# UnitEconomics
# ---------------------------------------------------------------------------

class TestUnitEconomics:

    def test_get_margin_returns_required_keys(self, ue: UnitEconomics):
        result = ue.get_margin("home_services", "hvac")
        required = {
            "gross_margin_pct",
            "gross_profit_per_lead",
            "cac_to_ltv_ratio",
            "payback_period_months",
        }
        assert required == set(result.keys())

    def test_get_margin_values_are_valid(self, ue: UnitEconomics):
        result = ue.get_margin("home_services", "hvac")
        assert 0.0 < result["gross_margin_pct"] < 1.0
        assert result["gross_profit_per_lead"] > 0
        assert result["cac_to_ltv_ratio"] > 0
        assert result["payback_period_months"] > 0

    def test_get_margin_math(self, ue: UnitEconomics):
        # hvac: lead_price=185, cac=45 => gross_profit=140, margin=140/185
        result = ue.get_margin("home_services", "hvac")
        expected_profit = 185.0 - 45.0
        expected_margin = expected_profit / 185.0
        assert result["gross_profit_per_lead"] == pytest.approx(expected_profit, rel=1e-3)
        assert result["gross_margin_pct"] == pytest.approx(expected_margin, rel=1e-3)

    def test_get_margin_real_estate(self, ue: UnitEconomics):
        result = ue.get_margin("real_estate", "dscr_loan")
        assert result["gross_margin_pct"] > 0

    def test_get_margin_b2b(self, ue: UnitEconomics):
        result = ue.get_margin("b2b", "enterprise")
        assert result["gross_margin_pct"] > 0

    def test_get_margin_invalid_vertical(self, ue: UnitEconomics):
        with pytest.raises(ValueError, match="Unknown vertical"):
            ue.get_margin("nonexistent", "hvac")

    def test_get_margin_invalid_sub_vertical(self, ue: UnitEconomics):
        with pytest.raises(ValueError, match="Unknown sub_vertical"):
            ue.get_margin("home_services", "nonexistent")

    def test_rank_sub_verticals_returns_sorted_list(self, ue: UnitEconomics):
        ranked = ue.rank_sub_verticals_by_margin("home_services")
        assert len(ranked) == len(VERTICAL_ECONOMICS["home_services"])
        margins = [r["gross_margin_pct"] for r in ranked]
        assert margins == sorted(margins, reverse=True)

    def test_rank_sub_verticals_contains_required_keys(self, ue: UnitEconomics):
        ranked = ue.rank_sub_verticals_by_margin("real_estate")
        for row in ranked:
            assert "sub_vertical" in row
            assert "vertical" in row
            assert "gross_margin_pct" in row
            assert "lead_price" in row
            assert "cac" in row

    def test_rank_sub_verticals_invalid_vertical(self, ue: UnitEconomics):
        with pytest.raises(ValueError):
            ue.rank_sub_verticals_by_margin("invalid")

    def test_calculate_ltv_to_cac(self, ue: UnitEconomics):
        ratio = ue.calculate_ltv_to_cac("home_services", "hvac")
        # hvac: ltv=20000, cac=45 => ratio ≈ 444.44
        assert ratio == pytest.approx(20000.0 / 45.0, rel=1e-2)

    def test_get_top_verticals_returns_n_items(self, ue: UnitEconomics):
        top5 = ue.get_top_verticals(n=5)
        assert len(top5) == 5

    def test_get_top_verticals_is_sorted(self, ue: UnitEconomics):
        top = ue.get_top_verticals(n=10)
        margins = [r["gross_margin_pct"] for r in top]
        assert margins == sorted(margins, reverse=True)

    def test_get_top_verticals_default_n(self, ue: UnitEconomics):
        top = ue.get_top_verticals()
        assert len(top) == 5

    def test_get_top_verticals_all(self, ue: UnitEconomics):
        total_sv = sum(len(v) for v in VERTICAL_ECONOMICS.values())
        top = ue.get_top_verticals(n=total_sv)
        assert len(top) == total_sv


# ---------------------------------------------------------------------------
# BreakEvenCalculator — platform
# ---------------------------------------------------------------------------

class TestBreakEvenCalculator:

    def test_calculate_platform_breakeven_returns_required_keys(self, be: BreakEvenCalculator):
        result = be.calculate_platform_breakeven()
        required = {
            "total_fixed_costs",
            "total_variable_costs",
            "total_revenue",
            "gross_profit",
            "gross_margin_pct",
            "break_even_leads",
            "break_even_revenue",
            "current_profit_loss",
            "months_to_profitability",
            "per_vertical_breakdown",
        }
        assert required == set(result.keys())

    def test_calculate_platform_breakeven_math(self, be: BreakEvenCalculator):
        # 10 HVAC leads: revenue=1850, variable=450, gross=1400
        lead_mix = [{"vertical": "home_services", "sub_vertical": "hvac", "volume": 10}]
        fixed = {"test": 500.0}
        result = be.calculate_platform_breakeven(
            monthly_fixed_costs=fixed,
            lead_mix=lead_mix,
        )
        assert result["total_revenue"] == pytest.approx(1850.0, rel=1e-3)
        assert result["total_variable_costs"] == pytest.approx(450.0, rel=1e-3)
        assert result["gross_profit"] == pytest.approx(1400.0, rel=1e-3)
        assert result["current_profit_loss"] == pytest.approx(900.0, rel=1e-3)  # 1400 - 500

    def test_calculate_platform_breakeven_gross_margin(self, be: BreakEvenCalculator):
        lead_mix = [{"vertical": "home_services", "sub_vertical": "hvac", "volume": 10}]
        result = be.calculate_platform_breakeven(
            monthly_fixed_costs={"test": 0.0},
            lead_mix=lead_mix,
        )
        assert 0.0 < result["gross_margin_pct"] < 1.0

    def test_calculate_platform_breakeven_default_costs(self, be: BreakEvenCalculator):
        result = be.calculate_platform_breakeven()
        expected_fixed = sum(DEFAULT_FIXED_COSTS.values())
        assert result["total_fixed_costs"] == pytest.approx(expected_fixed, rel=1e-3)

    def test_calculate_platform_breakeven_empty_mix(self, be: BreakEvenCalculator):
        result = be.calculate_platform_breakeven(
            monthly_fixed_costs={"test": 100.0},
            lead_mix=[{"vertical": "home_services", "sub_vertical": "hvac", "volume": 0}],
        )
        assert result["total_revenue"] == pytest.approx(0.0, abs=1e-3)

    # ------------------------------------------------------------------
    # Buyer break-even
    # ------------------------------------------------------------------

    def test_calculate_buyer_breakeven_returns_required_keys(self, be: BreakEvenCalculator):
        result = be.calculate_buyer_breakeven(
            lead_price=350.0,
            close_rate=0.20,
            avg_deal_value=1_000_000.0,
            origination_pct=0.015,
        )
        required = {
            "revenue_per_closed_lead",
            "cost_per_closed_lead",
            "roi_per_lead",
            "leads_to_break_even",
            "monthly_investment",
            "monthly_revenue_at_break_even",
            "payback_period_days",
        }
        assert required == set(result.keys())

    def test_calculate_buyer_breakeven_roi_is_positive(self, be: BreakEvenCalculator):
        # DSCR loan: 0.20 close rate, 1M deal, 1.5% origination
        # revenue per lead = 0.20 * 1M * 0.015 = 3000 >> 350 lead price
        result = be.calculate_buyer_breakeven(
            lead_price=350.0,
            close_rate=0.20,
            avg_deal_value=1_000_000.0,
            origination_pct=0.015,
        )
        assert result["roi_per_lead"] > 0

    def test_calculate_buyer_breakeven_cost_per_closed(self, be: BreakEvenCalculator):
        result = be.calculate_buyer_breakeven(
            lead_price=350.0,
            close_rate=0.20,
            avg_deal_value=1_000_000.0,
        )
        expected_cost = 350.0 / 0.20
        assert result["cost_per_closed_lead"] == pytest.approx(expected_cost, rel=1e-3)

    def test_calculate_buyer_breakeven_invalid_close_rate(self, be: BreakEvenCalculator):
        with pytest.raises(ValueError, match="close_rate"):
            be.calculate_buyer_breakeven(
                lead_price=350.0,
                close_rate=0.0,
                avg_deal_value=1_000_000.0,
            )

    def test_calculate_buyer_breakeven_payback_positive(self, be: BreakEvenCalculator):
        result = be.calculate_buyer_breakeven(
            lead_price=150.0,
            close_rate=0.20,
            avg_deal_value=700.0,
        )
        assert result["payback_period_days"] > 0

    # ------------------------------------------------------------------
    # Sensitivity analysis
    # ------------------------------------------------------------------

    def test_sensitivity_analysis_returns_correct_steps(self, be: BreakEvenCalculator):
        base = {
            "lead_price": 350.0,
            "close_rate": 0.20,
            "avg_deal_value": 1_000_000.0,
            "origination_pct": 0.015,
        }
        results = be.sensitivity_analysis(base, variable="close_rate", range_pct=0.30)
        # 11 points (0..10 inclusive), all close_rate > 0 so no filtering
        assert len(results) == 11

    def test_sensitivity_analysis_varies_variable(self, be: BreakEvenCalculator):
        base = {
            "lead_price": 350.0,
            "close_rate": 0.50,
            "avg_deal_value": 1_000_000.0,
            "origination_pct": 0.015,
        }
        results = be.sensitivity_analysis(base, variable="lead_price", range_pct=0.30)
        prices = [r["lead_price"] for r in results]
        assert min(prices) < base["lead_price"] < max(prices)

    def test_sensitivity_analysis_invalid_variable(self, be: BreakEvenCalculator):
        base = {
            "lead_price": 350.0,
            "close_rate": 0.20,
            "avg_deal_value": 1_000_000.0,
        }
        with pytest.raises(ValueError):
            be.sensitivity_analysis(base, variable="invalid_var")

    def test_sensitivity_analysis_result_keys(self, be: BreakEvenCalculator):
        base = {
            "lead_price": 350.0,
            "close_rate": 0.30,
            "avg_deal_value": 1_000_000.0,
            "origination_pct": 0.015,
        }
        results = be.sensitivity_analysis(base, variable="avg_deal_value")
        assert all("roi_per_lead" in r for r in results)
        assert all("current_profit_loss" in r for r in results)


# ---------------------------------------------------------------------------
# RevenueProjections
# ---------------------------------------------------------------------------

class TestRevenueProjections:

    def test_build_12_month_has_12_rows(self, rp: RevenueProjections):
        df = rp.build_12_month_projection()
        assert len(df) == 12

    def test_build_12_month_has_all_columns(self, rp: RevenueProjections):
        required_cols = {
            "Month", "New_Buyers", "Churned_Buyers", "Active_Buyers",
            "Leads_Delivered", "Gross_Revenue", "COGS", "Gross_Profit",
            "Operating_Expenses", "Net_Profit", "Cumulative_Revenue", "MRR",
        }
        df = rp.build_12_month_projection()
        assert required_cols.issubset(set(df.columns))

    def test_build_12_month_revenue_grows(self, rp: RevenueProjections):
        df = rp.build_12_month_projection(monthly_buyer_growth_rate=0.15)
        assert df["Gross_Revenue"].iloc[-1] > df["Gross_Revenue"].iloc[0]

    def test_build_12_month_cumulative_revenue_increases(self, rp: RevenueProjections):
        df = rp.build_12_month_projection()
        assert (df["Cumulative_Revenue"].diff().dropna() >= 0).all()

    def test_build_12_month_cogs_fraction(self, rp: RevenueProjections):
        df = rp.build_12_month_projection()
        cogs_ratio = (df["COGS"] / df["Gross_Revenue"]).round(2)
        expected = RevenueProjections.COGS_PCT
        assert all(abs(v - expected) < 0.01 for v in cogs_ratio)

    def test_calculate_metrics_summary_returns_required_keys(self, rp: RevenueProjections):
        df = rp.build_12_month_projection()
        summary = rp.calculate_metrics_summary(df)
        required = {
            "total_12m_revenue",
            "total_12m_profit",
            "peak_mrr",
            "avg_gross_margin",
            "ltv_per_buyer",
            "cac_blended",
            "ltv_to_cac_ratio",
            "break_even_month",
        }
        assert required == set(summary.keys())

    def test_calculate_metrics_summary_values(self, rp: RevenueProjections):
        df = rp.build_12_month_projection()
        summary = rp.calculate_metrics_summary(df)
        assert summary["total_12m_revenue"] > 0
        assert summary["peak_mrr"] > 0
        assert 0.0 <= summary["avg_gross_margin"] <= 1.0

    def test_build_scenario_comparison_returns_3_scenarios(self, rp: RevenueProjections):
        df = rp.build_scenario_comparison()
        assert len(df) == 3

    def test_build_scenario_comparison_has_scenario_col(self, rp: RevenueProjections):
        df = rp.build_scenario_comparison()
        assert "scenario" in df.columns

    def test_build_scenario_comparison_aggressive_higher_revenue(self, rp: RevenueProjections):
        df = rp.build_scenario_comparison()
        revenues = df.set_index("scenario")["total_12m_revenue"]
        assert revenues["Aggressive"] > revenues["Base"] > revenues["Conservative"]

    def test_build_scenario_comparison_custom_scenarios(self, rp: RevenueProjections):
        scenarios = [
            {"name": "Slow",   "monthly_buyer_growth_rate": 0.05},
            {"name": "Medium", "monthly_buyer_growth_rate": 0.10},
        ]
        df = rp.build_scenario_comparison(scenarios=scenarios)
        assert len(df) == 2
        assert set(df["scenario"]) == {"Slow", "Medium"}
