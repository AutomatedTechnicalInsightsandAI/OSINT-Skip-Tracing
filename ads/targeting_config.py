"""
Targeting configuration for Google and Meta ad campaigns.

Contains Florida metro areas, keyword themes by sub-vertical,
bid recommendations, negative keyword lists, and audience segments.
"""

from __future__ import annotations


class TargetingConfig:
    """Static targeting data for ad campaign generation."""

    FLORIDA_METROS: dict[str, list[str]] = {
        "Tampa Bay": ["Tampa", "St. Petersburg", "Clearwater", "Brandon", "Largo"],
        "Miami": ["Miami", "Coral Gables", "Hialeah", "Doral", "Miami Gardens"],
        "Orlando": ["Orlando", "Kissimmee", "Sanford", "Deltona", "Altamonte Springs"],
        "Fort Lauderdale": ["Fort Lauderdale", "Pompano Beach", "Hollywood", "Coral Springs"],
        "Jacksonville": ["Jacksonville", "Orange Park", "Fleming Island", "Ponte Vedra"],
        "Sarasota": ["Sarasota", "Bradenton", "Venice", "North Port", "Englewood"],
        "Naples": ["Naples", "Bonita Springs", "Marco Island", "Estero"],
        "West Palm Beach": ["West Palm Beach", "Boca Raton", "Delray Beach", "Boynton Beach"],
    }

    KEYWORD_THEMES: dict[str, list[str]] = {
        "hvac": ["ac repair", "hvac service", "air conditioning repair", "ac replacement", "hvac contractor"],
        "roofing": ["roof repair", "roofing contractor", "roof replacement", "roofing company", "new roof"],
        "solar": ["solar panels", "solar installation", "solar energy", "go solar", "solar company"],
        "plumbing": ["plumber", "plumbing repair", "emergency plumber", "plumbing service", "drain cleaning"],
        "electrical": ["electrician", "electrical repair", "electrical contractor", "panel upgrade", "rewiring"],
        "water_damage": ["water damage restoration", "flood cleanup", "water damage repair", "mold remediation"],
        "windows": ["window replacement", "window installation", "new windows", "impact windows", "window company"],
        "pest_control": ["pest control", "exterminator", "termite treatment", "bug control", "pest removal"],
        "dscr_loan": ["dscr loan", "rental property loan", "investor mortgage", "no income verification loan"],
        "hard_money": ["hard money lender", "hard money loan", "fix and flip loan", "rehab loan"],
        "fix_and_flip": ["fix and flip financing", "rehab loan", "fix flip loan", "house flip loan"],
        "bridge_loan": ["bridge loan", "bridge financing", "short term real estate loan"],
        "commercial_re": ["commercial real estate loan", "commercial mortgage", "commercial property financing"],
        "wholesale_buyer": ["wholesale real estate", "buy houses cash", "we buy houses", "cash home buyer"],
        "smb": ["small business leads", "b2b lead generation", "local business marketing"],
        "mid_market": ["mid market leads", "b2b sales leads", "business development leads"],
        "enterprise": ["enterprise leads", "enterprise sales", "b2b enterprise solutions"],
    }

    BID_RECOMMENDATIONS: dict[str, dict[str, float]] = {
        "hvac": {"target_cpa": 185.0, "max_cpc": 35.0, "daily_budget": 75.0},
        "roofing": {"target_cpa": 225.0, "max_cpc": 42.0, "daily_budget": 90.0},
        "solar": {"target_cpa": 275.0, "max_cpc": 50.0, "daily_budget": 110.0},
        "plumbing": {"target_cpa": 125.0, "max_cpc": 25.0, "daily_budget": 55.0},
        "electrical": {"target_cpa": 150.0, "max_cpc": 30.0, "daily_budget": 65.0},
        "water_damage": {"target_cpa": 300.0, "max_cpc": 55.0, "daily_budget": 120.0},
        "windows": {"target_cpa": 175.0, "max_cpc": 33.0, "daily_budget": 70.0},
        "pest_control": {"target_cpa": 85.0, "max_cpc": 18.0, "daily_budget": 40.0},
        "dscr_loan": {"target_cpa": 350.0, "max_cpc": 65.0, "daily_budget": 140.0},
        "hard_money": {"target_cpa": 450.0, "max_cpc": 80.0, "daily_budget": 180.0},
        "fix_and_flip": {"target_cpa": 300.0, "max_cpc": 55.0, "daily_budget": 120.0},
        "bridge_loan": {"target_cpa": 400.0, "max_cpc": 72.0, "daily_budget": 160.0},
        "commercial_re": {"target_cpa": 700.0, "max_cpc": 120.0, "daily_budget": 280.0},
        "wholesale_buyer": {"target_cpa": 200.0, "max_cpc": 38.0, "daily_budget": 80.0},
        "smb": {"target_cpa": 150.0, "max_cpc": 28.0, "daily_budget": 60.0},
        "mid_market": {"target_cpa": 500.0, "max_cpc": 90.0, "daily_budget": 200.0},
        "enterprise": {"target_cpa": 1200.0, "max_cpc": 200.0, "daily_budget": 480.0},
    }

    NEGATIVE_KEYWORDS: dict[str, list[str]] = {
        "home_services": ["diy", "free", "how to", "youtube", "tutorial", "cheap", "used"],
        "real_estate": ["residential", "rental listing", "zillow", "redfin", "apartment search", "for sale by owner"],
        "b2b": ["job", "career", "hiring", "employment", "internship", "salary"],
    }

    AUDIENCE_SEGMENTS: dict[str, dict[str, list[str]]] = {
        "home_services": {
            "interests": ["Home improvement", "Real estate", "DIY projects", "Home ownership"],
            "behaviors": ["Homeowners", "Recently moved"],
        },
        "real_estate": {
            "interests": ["Real estate investing", "Investment properties", "Financial planning", "Entrepreneurship"],
            "behaviors": ["Real estate investors", "Small business owners"],
        },
        "b2b": {
            "interests": ["Business", "Entrepreneurship", "Sales", "Marketing", "Finance"],
            "behaviors": ["Business page admins", "Small business owners"],
        },
    }
