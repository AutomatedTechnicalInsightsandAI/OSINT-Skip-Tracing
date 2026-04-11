"""
Campaign builder — assembles complete multi-channel ad campaign packages.

Combines Google RSA and Meta ad copy with budget allocation, expected
performance metrics, A/B test variants, landing page recommendations,
and conversion tracking setup.
"""

from __future__ import annotations

import math

from ads.ad_copy_generator import AdCopyGenerator
from ads.targeting_config import TargetingConfig

# Budget split ratios by vertical category
_BUDGET_SPLITS: dict[str, dict[str, float]] = {
    "home_services": {"google_pct": 0.70, "meta_pct": 0.30},
    "real_estate":   {"google_pct": 0.60, "meta_pct": 0.40},
    "b2b":           {"google_pct": 0.55, "meta_pct": 0.45},
}

# Category mapping (sub_vertical → category)
_VERTICAL_CATEGORY: dict[str, str] = {
    "hvac": "home_services",
    "roofing": "home_services",
    "solar": "home_services",
    "plumbing": "home_services",
    "electrical": "home_services",
    "water_damage": "home_services",
    "windows": "home_services",
    "pest_control": "home_services",
    "dscr_loan": "real_estate",
    "hard_money": "real_estate",
    "fix_and_flip": "real_estate",
    "bridge_loan": "real_estate",
    "commercial_re": "real_estate",
    "wholesale_buyer": "real_estate",
    "smb": "b2b",
    "mid_market": "b2b",
    "enterprise": "b2b",
}

# Assumed click-through and conversion rates for estimations
_BENCHMARK_CTR: float = 0.05        # 5 % Google CTR
_BENCHMARK_CVR: float = 0.08        # 8 % landing page CVR
_COST_PER_IMPRESSION: float = 0.01  # $10 CPM equivalent


class CampaignBuilder:
    """Assembles full multi-channel campaign packages for any sub-vertical."""

    def __init__(self) -> None:
        self._generator = AdCopyGenerator()

    def build_full_campaign_package(
        self,
        vertical: str,
        sub_vertical: str,
        location: str,
        monthly_budget: float,
    ) -> dict:
        """
        Build a complete campaign package for the given sub-vertical and location.

        Args:
            vertical: Top-level vertical (e.g. ``"home_services"``).
            sub_vertical: Sub-vertical key (e.g. ``"hvac"``).
            location: Target Florida metro (e.g. ``"Tampa Bay"``).
            monthly_budget: Total monthly ad spend in USD.

        Returns:
            A dict containing Google and Meta campaign configs, budget split,
            expected metrics, A/B test variant, landing page recommendations,
            and conversion tracking setup.
        """
        category = _VERTICAL_CATEGORY.get(sub_vertical, vertical)
        split_ratios = _BUDGET_SPLITS.get(category, {"google_pct": 0.60, "meta_pct": 0.40})

        google_monthly = round(monthly_budget * split_ratios["google_pct"], 2)
        meta_monthly = round(monthly_budget * split_ratios["meta_pct"], 2)

        google_campaign = self._generator.generate_google_rsa(vertical, sub_vertical, location)
        meta_campaign = self._generator.generate_meta_ad(vertical, sub_vertical, location)
        ab_variant = self._generator.generate_meta_ad_variant_b(vertical, sub_vertical, location)

        bid_recs = TargetingConfig.BID_RECOMMENDATIONS.get(sub_vertical, {})
        target_cpa = bid_recs.get("target_cpa", 200.0)
        max_cpc = bid_recs.get("max_cpc", 30.0)

        # Rough impression / click / lead estimates
        estimated_impressions = math.floor(monthly_budget / _COST_PER_IMPRESSION)
        estimated_clicks = math.floor(estimated_impressions * _BENCHMARK_CTR)
        estimated_leads = math.floor(estimated_clicks * _BENCHMARK_CVR)
        estimated_cpl = round(monthly_budget / estimated_leads, 2) if estimated_leads > 0 else 0.0

        return {
            "vertical": vertical,
            "sub_vertical": sub_vertical,
            "location": location,
            "monthly_budget": monthly_budget,
            "google_campaign": google_campaign,
            "meta_campaign": meta_campaign,
            "budget_split": {
                "google_pct": split_ratios["google_pct"],
                "meta_pct": split_ratios["meta_pct"],
                "google_monthly": google_monthly,
                "meta_monthly": meta_monthly,
            },
            "expected_metrics": {
                "estimated_impressions": estimated_impressions,
                "estimated_clicks": estimated_clicks,
                "estimated_leads": estimated_leads,
                "estimated_cpl": estimated_cpl,
            },
            "ab_test_variant": ab_variant,
            "landing_page_recommendations": self._landing_page_recs(sub_vertical),
            "conversion_tracking": self._conversion_tracking(sub_vertical),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _landing_page_recs(self, sub_vertical: str) -> list[str]:
        """Return landing page best-practice recommendations for the sub-vertical."""
        category = _VERTICAL_CATEGORY.get(sub_vertical, "home_services")
        common = [
            "Load time under 2 seconds (mobile-first)",
            "Phone number prominently in header — click-to-call enabled",
            "Trust signals: licenses, insurance badges, 5-star reviews",
            "Single clear CTA above the fold",
            "Lead form with ≤5 fields",
        ]
        specific: dict[str, list[str]] = {
            "home_services": [
                "Add a 'Same-Day Service Available' urgency banner",
                "Include a before/after photo gallery",
                "Display service area zip code checker",
            ],
            "real_estate": [
                "Include a loan calculator or quick-quote form",
                "Show deal examples with funded amounts",
                "Add 'Close in X Days' counter to create urgency",
            ],
            "b2b": [
                "Show sample lead file with blurred data for social proof",
                "Include a free sample offer or demo button",
                "Display client logos and case study snippets",
            ],
        }
        return common + specific.get(category, [])

    def _conversion_tracking(self, sub_vertical: str) -> list[str]:
        """Return recommended conversion tracking events for the sub-vertical."""
        category = _VERTICAL_CATEGORY.get(sub_vertical, "home_services")
        base = [
            "Google Ads: Form submission (primary conversion)",
            "Google Ads: Phone call from ad (≥60 seconds)",
            "Google Ads: Phone call from website (≥60 seconds)",
            "Meta: Lead form submission event",
            "Meta: Contact button click",
        ]
        extra: dict[str, list[str]] = {
            "home_services": [
                "Meta: Schedule appointment event",
                "Google Analytics 4: booking_started event",
            ],
            "real_estate": [
                "Meta: Apply Now button click",
                "Google Analytics 4: application_started event",
                "CRM: Lead stage = 'Pre-Approved'",
            ],
            "b2b": [
                "Meta: Download sample file event",
                "Google Analytics 4: sample_download event",
                "CRM: Lead stage = 'Demo Scheduled'",
            ],
        }
        return base + extra.get(category, [])
