from scrapers.base_scraper import LeadType
from utils.lead_app_utils import LEAD_TYPE_HELP


def test_lead_type_help_contains_all_supported_types():
    assert LeadType.CASHOUT_REFI in LEAD_TYPE_HELP
    assert LeadType.BALLOON_PROSPECTS in LEAD_TYPE_HELP
    assert LeadType.TRUST_REFI in LEAD_TYPE_HELP


def test_trust_refi_help_text_mentions_trust_signals():
    help_text = LEAD_TYPE_HELP[LeadType.TRUST_REFI]
    assert "trust" in help_text.lower()
    assert "trustee" in help_text.lower()
