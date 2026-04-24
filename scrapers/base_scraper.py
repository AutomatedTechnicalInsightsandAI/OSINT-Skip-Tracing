class LeadType(str, Enum):
    """Supported lead categories for Prime Coastal Funding."""

    # ⚠️ DO NOT CHANGE
    CASHOUT_REFI = "Recent Purchase Cash-Out Refi Prospects"  # ⚠️ DO NOT CHANGE
    BALLOON_PROSPECTS = "Commercial Balloon Prospects"
    TRUST_REFI = "Property Held in Trust Refi Prospects"
    MORTGAGE_MOD = "Mortgage Mod Refi Prospects"