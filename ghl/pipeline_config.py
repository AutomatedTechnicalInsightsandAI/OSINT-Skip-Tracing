"""
GoHighLevel Pipeline Configuration
===================================

All pipeline IDs, stage IDs, and lead values are driven by environment
variables so no secrets or environment-specific IDs are hard-coded.

Usage::

    from ghl.pipeline_config import HOME_SERVICES_PIPELINE, REAL_ESTATE_PIPELINE, B2B_PIPELINE
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Home Services Pipeline
# ---------------------------------------------------------------------------

HOME_SERVICES_PIPELINE: dict = {
    "pipeline_id": os.getenv("GHL_HS_PIPELINE_ID", "hs_pipeline_001"),
    "stages": {
        "new_lead":         os.getenv("GHL_HS_STAGE_NEW",  "stage_hs_01"),
        "qualified":        os.getenv("GHL_HS_STAGE_QUAL", "stage_hs_02"),
        "appointment_set":  os.getenv("GHL_HS_STAGE_APPT", "stage_hs_03"),
        "appointment_kept": os.getenv("GHL_HS_STAGE_KEPT", "stage_hs_04"),
        "estimate_sent":    os.getenv("GHL_HS_STAGE_EST",  "stage_hs_05"),
        "closed_won":       os.getenv("GHL_HS_STAGE_WON",  "stage_hs_06"),
        "closed_lost":      os.getenv("GHL_HS_STAGE_LOST", "stage_hs_07"),
    },
    "lead_values": {
        "hvac":         185.0,
        "roofing":      225.0,
        "plumbing":     125.0,
        "solar":        275.0,
        "electrical":   150.0,
        "water_damage": 300.0,
        "windows":      175.0,
        "pest_control":  85.0,
    },
}

# ---------------------------------------------------------------------------
# Real Estate / Mortgage Pipeline
# ---------------------------------------------------------------------------

REAL_ESTATE_PIPELINE: dict = {
    "pipeline_id": os.getenv("GHL_RE_PIPELINE_ID", "re_pipeline_001"),
    "stages": {
        "new_lead":        os.getenv("GHL_RE_STAGE_NEW",  "stage_re_01"),
        "pre_qualified":   os.getenv("GHL_RE_STAGE_PREQ", "stage_re_02"),
        "qualified":       os.getenv("GHL_RE_STAGE_QUAL", "stage_re_03"),
        "docs_requested":  os.getenv("GHL_RE_STAGE_DOCS", "stage_re_04"),
        "term_sheet_sent": os.getenv("GHL_RE_STAGE_TERM", "stage_re_05"),
        "under_contract":  os.getenv("GHL_RE_STAGE_CONT", "stage_re_06"),
        "closed_funded":   os.getenv("GHL_RE_STAGE_FUND", "stage_re_07"),
        "closed_lost":     os.getenv("GHL_RE_STAGE_LOST", "stage_re_08"),
    },
    "lead_values": {
        "dscr_loan":              350.0,
        "hard_money":             450.0,
        "fix_and_flip":           300.0,
        "bridge_loan":            400.0,
        "commercial_re":          700.0,
        "wholesale_buyer":        200.0,
        "apartment_syndication":  900.0,
    },
}

# ---------------------------------------------------------------------------
# B2B Pipeline
# ---------------------------------------------------------------------------

B2B_PIPELINE: dict = {
    "pipeline_id": os.getenv("GHL_B2B_PIPELINE_ID", "b2b_pipeline_001"),
    "stages": {
        "new_lead":       os.getenv("GHL_B2B_STAGE_NEW",  "stage_b2b_01"),
        "contacted":      os.getenv("GHL_B2B_STAGE_CONT", "stage_b2b_02"),
        "qualified":      os.getenv("GHL_B2B_STAGE_QUAL", "stage_b2b_03"),
        "demo_scheduled": os.getenv("GHL_B2B_STAGE_DEMO", "stage_b2b_04"),
        "proposal_sent":  os.getenv("GHL_B2B_STAGE_PROP", "stage_b2b_05"),
        "negotiation":    os.getenv("GHL_B2B_STAGE_NEG",  "stage_b2b_06"),
        "closed_won":     os.getenv("GHL_B2B_STAGE_WON",  "stage_b2b_07"),
        "closed_lost":    os.getenv("GHL_B2B_STAGE_LOST", "stage_b2b_08"),
    },
    "lead_values": {
        "smb":        500.0,
        "mid_market": 2500.0,
        "enterprise": 10000.0,
    },
}

# Convenience map: vertical string → pipeline config dict
PIPELINE_MAP: dict[str, dict] = {
    "home_services": HOME_SERVICES_PIPELINE,
    "real_estate":   REAL_ESTATE_PIPELINE,
    "b2b":           B2B_PIPELINE,
}
