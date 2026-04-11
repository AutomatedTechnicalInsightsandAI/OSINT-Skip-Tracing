"""
financials/unit_economics.py
=============================
Unit economics data and calculations for all platform verticals.

All margin data is hard-coded from the business model. Adjust the
``VERTICAL_ECONOMICS`` dict to update any assumption platform-wide.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

VERTICAL_ECONOMICS: dict[str, dict[str, dict[str, Any]]] = {
    "home_services": {
        "hvac":         {"lead_price": 185.0, "cac": 45.0,  "ltv": 20000.0, "close_rate": 0.30, "avg_job": 11500.0},
        "roofing":      {"lead_price": 225.0, "cac": 55.0,  "ltv": 21000.0, "close_rate": 0.25, "avg_job": 20000.0},
        "solar":        {"lead_price": 275.0, "cac": 70.0,  "ltv": 40000.0, "close_rate": 0.20, "avg_job": 35000.0},
        "plumbing":     {"lead_price": 125.0, "cac": 30.0,  "ltv": 5500.0,  "close_rate": 0.35, "avg_job": 3500.0},
        "electrical":   {"lead_price": 150.0, "cac": 38.0,  "ltv": 8500.0,  "close_rate": 0.28, "avg_job": 6000.0},
        "water_damage": {"lead_price": 300.0, "cac": 75.0,  "ltv": 10000.0, "close_rate": 0.22, "avg_job": 12000.0},
        "windows":      {"lead_price": 175.0, "cac": 42.0,  "ltv": 13000.0, "close_rate": 0.25, "avg_job": 13000.0},
        "pest_control": {"lead_price": 85.0,  "cac": 20.0,  "ltv": 3600.0,  "close_rate": 0.40, "avg_job": 800.0},
    },
    "real_estate": {
        "dscr_loan":       {"lead_price": 350.0, "cac": 90.0,  "ltv": 60000.0,  "close_rate": 0.20, "avg_deal": 1000000.0, "origination_pct": 0.015},
        "hard_money":      {"lead_price": 450.0, "cac": 110.0, "ltv": 115000.0, "close_rate": 0.18, "avg_deal": 500000.0,  "origination_pct": 0.030},
        "fix_and_flip":    {"lead_price": 300.0, "cac": 75.0,  "ltv": 47500.0,  "close_rate": 0.22, "avg_deal": 400000.0,  "origination_pct": 0.025},
        "bridge_loan":     {"lead_price": 400.0, "cac": 100.0, "ltv": 55000.0,  "close_rate": 0.18, "avg_deal": 750000.0,  "origination_pct": 0.020},
        "commercial_re":   {"lead_price": 700.0, "cac": 175.0, "ltv": 255000.0, "close_rate": 0.15, "avg_deal": 3000000.0, "origination_pct": 0.015},
        "wholesale_buyer": {"lead_price": 200.0, "cac": 50.0,  "ltv": 62500.0,  "close_rate": 0.25, "avg_deal": 250000.0,  "origination_pct": 0.0},
    },
    "b2b": {
        "smb":        {"lead_price": 150.0,  "cac": 40.0,  "ltv": 8400.0,   "close_rate": 0.20, "avg_contract": 700.0,   "retention_months": 12},
        "mid_market": {"lead_price": 500.0,  "cac": 125.0, "ltv": 75000.0,  "close_rate": 0.15, "avg_contract": 5000.0,  "retention_months": 15},
        "enterprise": {"lead_price": 1200.0, "cac": 300.0, "ltv": 360000.0, "close_rate": 0.10, "avg_contract": 20000.0, "retention_months": 18},
    },
}


class UnitEconomics:
    """
    Provides unit-economics calculations for all platform verticals.

    All source data lives in ``VERTICAL_ECONOMICS``. Methods return
    plain Python dicts / lists so they can be used independently of
    Streamlit or pandas.
    """

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_margin(self, vertical: str, sub_vertical: str) -> dict[str, float]:
        """
        Return margin metrics for a single sub-vertical.

        Parameters
        ----------
        vertical:
            Top-level vertical key, e.g. ``"home_services"``.
        sub_vertical:
            Sub-vertical key, e.g. ``"hvac"``.

        Returns
        -------
        dict with keys:
            - ``gross_margin_pct``       — (lead_price - cac) / lead_price
            - ``gross_profit_per_lead``  — lead_price - cac
            - ``cac_to_ltv_ratio``       — cac / ltv
            - ``payback_period_months``  — cac / (close_rate * avg_value / 12)
        """
        data = self._get_data(vertical, sub_vertical)
        lead_price: float = data["lead_price"]
        cac: float = data["cac"]
        ltv: float = data["ltv"]
        close_rate: float = data["close_rate"]

        gross_profit = lead_price - cac
        gross_margin_pct = gross_profit / lead_price if lead_price else 0.0
        cac_to_ltv_ratio = cac / ltv if ltv else 0.0

        # avg_value is the revenue generated per closed deal
        avg_value = self._avg_value(data)
        monthly_value = close_rate * avg_value / 12.0
        payback_period_months = cac / monthly_value if monthly_value else float("inf")

        return {
            "gross_margin_pct": round(gross_margin_pct, 4),
            "gross_profit_per_lead": round(gross_profit, 2),
            "cac_to_ltv_ratio": round(cac_to_ltv_ratio, 6),
            "payback_period_months": round(payback_period_months, 2),
        }

    def rank_sub_verticals_by_margin(self, vertical: str) -> list[dict]:
        """
        Return all sub-verticals within *vertical* sorted by gross margin
        descending.

        Each element of the returned list is a dict with keys:
        ``sub_vertical``, ``vertical``, ``lead_price``, ``cac``, ``ltv``,
        ``close_rate``, plus all keys from :meth:`get_margin`.
        """
        if vertical not in VERTICAL_ECONOMICS:
            raise ValueError(f"Unknown vertical '{vertical}'")

        rows = []
        for sv, data in VERTICAL_ECONOMICS[vertical].items():
            margin = self.get_margin(vertical, sv)
            rows.append(
                {
                    "sub_vertical": sv,
                    "vertical": vertical,
                    "lead_price": data["lead_price"],
                    "cac": data["cac"],
                    "ltv": data["ltv"],
                    "close_rate": data["close_rate"],
                    **margin,
                }
            )

        return sorted(rows, key=lambda r: r["gross_margin_pct"], reverse=True)

    def calculate_ltv_to_cac(self, vertical: str, sub_vertical: str) -> float:
        """
        Return the LTV : CAC ratio for a sub-vertical.

        A ratio > 3 is generally considered healthy for a SaaS-style
        business; for lead-gen the threshold can be lower.
        """
        data = self._get_data(vertical, sub_vertical)
        ltv: float = data["ltv"]
        cac: float = data["cac"]
        return round(ltv / cac, 2) if cac else float("inf")

    def get_top_verticals(self, n: int = 5) -> list[dict]:
        """
        Return the top *n* sub-verticals across **all** verticals, ranked
        by gross margin percentage descending.
        """
        all_rows: list[dict] = []
        for vertical in VERTICAL_ECONOMICS:
            all_rows.extend(self.rank_sub_verticals_by_margin(vertical))

        # Sort by gross margin descending, then break ties by gross profit
        all_rows.sort(
            key=lambda r: (r["gross_margin_pct"], r["gross_profit_per_lead"]),
            reverse=True,
        )
        return all_rows[:n]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_data(vertical: str, sub_vertical: str) -> dict[str, Any]:
        """Retrieve raw data dict; raise informative errors on bad keys."""
        if vertical not in VERTICAL_ECONOMICS:
            raise ValueError(f"Unknown vertical '{vertical}'")
        sv_map = VERTICAL_ECONOMICS[vertical]
        if sub_vertical not in sv_map:
            raise ValueError(
                f"Unknown sub_vertical '{sub_vertical}' in vertical '{vertical}'"
            )
        return sv_map[sub_vertical]

    @staticmethod
    def _avg_value(data: dict[str, Any]) -> float:
        """
        Extract the average deal / job / contract value regardless of
        the key name used in the data dict.
        """
        for key in ("avg_job", "avg_deal", "avg_contract"):
            if key in data:
                return float(data[key])
        return 0.0
