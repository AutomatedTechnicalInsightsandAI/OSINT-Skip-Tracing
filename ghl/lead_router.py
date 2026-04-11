"""
GoHighLevel Lead Router
========================

Routes scraped leads to the correct GHL pipeline based on the chosen vertical
and auto-detected sub-vertical.

Usage::

    from ghl.lead_router import LeadRouter

    router = LeadRouter()
    result = router.route(lead_dict, vertical="real_estate")
    if result.success:
        print(f"Contact created: {result.contact_id}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ghl.ghl_client import GHLClient
from ghl.pipeline_config import PIPELINE_MAP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sub-vertical detection maps
# ---------------------------------------------------------------------------

# Property-type keywords → home-services sub-vertical
_HS_PROPERTY_KEYWORDS: dict[str, str] = {
    "solar":         "solar",
    "hvac":          "hvac",
    "roof":          "roofing",
    "plumb":         "plumbing",
    "electric":      "electrical",
    "water damage":  "water_damage",
    "window":        "windows",
    "pest":          "pest_control",
}

# Lead-type / property-type keywords → real-estate sub-vertical
_RE_LEAD_TYPE_KEYWORDS: dict[str, str] = {
    "fix":            "fix_and_flip",
    "flip":           "fix_and_flip",
    "dscr":           "dscr_loan",
    "high interest":  "dscr_loan",
    "high equity":    "dscr_loan",
    "hard money":     "hard_money",
    "bridge":         "bridge_loan",
    "commercial":     "commercial_re",
    "wholesale":      "wholesale_buyer",
    "apartment":      "apartment_syndication",
    "multifamily":    "apartment_syndication",
    "multi-family":   "apartment_syndication",
    "past financing": "dscr_loan",
}

# ---------------------------------------------------------------------------
# DeliveryResult
# ---------------------------------------------------------------------------


@dataclass
class DeliveryResult:
    """Outcome of a single lead delivery attempt.

    Attributes
    ----------
    contact_id:
        GHL contact ID created or updated during routing.
    opportunity_id:
        GHL opportunity ID created for the lead.
    pipeline:
        Pipeline ID the lead was placed in.
    stage:
        Stage ID within the pipeline.
    tags_applied:
        List of tag strings applied to the contact.
    success:
        True when the full workflow completed without error.
    error:
        Error message if ``success`` is False, else None.
    """

    contact_id: str = ""
    opportunity_id: str = ""
    pipeline: str = ""
    stage: str = ""
    tags_applied: list[str] = field(default_factory=list)
    success: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# LeadRouter
# ---------------------------------------------------------------------------


class LeadRouter:
    """Routes a scraped lead dict into the correct GoHighLevel pipeline.

    Parameters
    ----------
    client:
        Optional pre-configured :class:`~ghl.ghl_client.GHLClient`.
        A new client will be created from environment variables if omitted.
    """

    def __init__(self, client: GHLClient | None = None) -> None:
        self._client = client or GHLClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, lead: dict, vertical: str) -> DeliveryResult:
        """Route a lead dict into the appropriate GHL pipeline.

        Parameters
        ----------
        lead:
            Scraped lead dictionary produced by the existing county scrapers /
            ``DataProcessor``.  Expected keys (all optional but used when
            present): ``Owner Name``, ``Property Address``, ``Mailing Address``,
            ``County``, ``Scraped Emails``, ``Lead Score``, ``Deal Size``,
            ``Property Type``, ``Assessed Value``, ``Equity``,
            ``Mortgage Balance``, ``Lead Source``, ``Lead Type``.
        vertical:
            One of ``"home_services"``, ``"real_estate"``, or ``"b2b"``.

        Returns
        -------
        DeliveryResult
            Populated result object.  ``success`` is True only when all API
            calls complete without error.
        """
        result = DeliveryResult()

        try:
            pipeline_cfg = PIPELINE_MAP.get(vertical)
            if pipeline_cfg is None:
                raise ValueError(
                    f"Unknown vertical '{vertical}'. "
                    f"Must be one of: {list(PIPELINE_MAP.keys())}"
                )

            sub_vertical = self._detect_sub_vertical(lead, vertical, pipeline_cfg)
            lead_value = pipeline_cfg["lead_values"].get(sub_vertical, 0.0)
            pipeline_id = pipeline_cfg["pipeline_id"]
            stage_id = pipeline_cfg["stages"]["new_lead"]

            # 1. Create contact
            contact_payload = self._build_contact_payload(lead)
            contact_resp = self._client.create_contact(contact_payload)
            contact_id = (
                contact_resp.get("contact", {}).get("id")
                or contact_resp.get("id", "")
            )
            result.contact_id = contact_id
            result.pipeline = pipeline_id
            result.stage = stage_id

            # 2. Create opportunity
            opp_name = self._build_opportunity_name(lead, vertical, sub_vertical)
            opp_resp = self._client.create_opportunity(
                contact_id=contact_id,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                value=lead_value,
                name=opp_name,
            )
            result.opportunity_id = (
                opp_resp.get("opportunity", {}).get("id")
                or opp_resp.get("id", "")
            )

            # 3. Apply tags
            tags = self._build_tags(lead, vertical, sub_vertical)
            if tags:
                self._client.add_tag(contact_id, tags)
            result.tags_applied = tags

            result.success = True
            logger.info(
                "Lead routed | contact=%s opp=%s pipeline=%s stage=%s tags=%s",
                contact_id,
                result.opportunity_id,
                pipeline_id,
                stage_id,
                tags,
            )

        except Exception as exc:  # noqa: BLE001
            result.success = False
            result.error = str(exc)
            logger.error("LeadRouter.route failed: %s", exc, exc_info=True)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_sub_vertical(
        self, lead: dict, vertical: str, pipeline_cfg: dict
    ) -> str:
        """Detect the sub-vertical from the lead data.

        Falls back to the first available key in ``pipeline_cfg["lead_values"]``.
        """
        lead_type = str(lead.get("Lead Type", "")).lower()
        property_type = str(lead.get("Property Type", "")).lower()
        combined = f"{lead_type} {property_type}"

        if vertical == "home_services":
            for keyword, sub in _HS_PROPERTY_KEYWORDS.items():
                if keyword in combined:
                    return sub

        elif vertical == "real_estate":
            for keyword, sub in _RE_LEAD_TYPE_KEYWORDS.items():
                if keyword in combined:
                    return sub

        elif vertical == "b2b":
            assessed = self._parse_float(lead.get("Assessed Value"))
            if assessed >= 1_000_000:
                return "enterprise"
            if assessed >= 250_000:
                return "mid_market"
            return "smb"

        # Default: first defined sub-vertical for this pipeline
        return next(iter(pipeline_cfg["lead_values"]))

    def _build_contact_payload(self, lead: dict) -> dict:
        """Map scraped lead fields to a GHL contact payload."""
        # Parse owner name into first / last
        raw_name = str(lead.get("Owner Name", "")).strip()
        parts = raw_name.split(None, 1)
        first_name = parts[0] if parts else raw_name
        last_name = parts[1] if len(parts) > 1 else ""

        # Address
        address = str(lead.get("Property Address", "")).strip()
        mailing = str(lead.get("Mailing Address", "")).strip()

        payload: dict = {
            "firstName": first_name,
            "lastName": last_name,
            "address1": mailing or address,
            "city": str(lead.get("City", "")).strip(),
            "state": str(lead.get("State", "FL")).strip() or "FL",
            "postalCode": str(lead.get("Zip", "")).strip(),
            "country": "US",
            "source": str(lead.get("Lead Source", "OSINT Scraper")).strip(),
            "customField": {
                "lead_score":      lead.get("Lead Score", ""),
                "deal_size":       lead.get("Deal Size", ""),
                "property_type":   lead.get("Property Type", ""),
                "assessed_value":  lead.get("Assessed Value", ""),
                "equity":          lead.get("Equity", ""),
                "mortgage_balance": lead.get("Mortgage Balance", ""),
                "lead_source":     lead.get("Lead Source", "OSINT Scraper"),
                "county":          lead.get("County", ""),
                "property_address": address,
            },
        }

        email = str(lead.get("Scraped Emails", "")).strip()
        if email:
            payload["email"] = email.split(",")[0].strip()

        phone = str(lead.get("Phone", "")).strip()
        if phone:
            payload["phone"] = phone

        return payload

    def _build_opportunity_name(
        self, lead: dict, vertical: str, sub_vertical: str
    ) -> str:
        """Generate a human-readable opportunity name."""
        owner = str(lead.get("Owner Name", "Unknown")).strip()
        address = str(lead.get("Property Address", "")).strip()
        sub_label = sub_vertical.replace("_", " ").title()
        if address:
            return f"{owner} — {sub_label} ({address})"
        return f"{owner} — {sub_label}"

    def _build_tags(
        self, lead: dict, vertical: str, sub_vertical: str
    ) -> list[str]:
        """Build the list of GHL tags to apply to the contact."""
        tags: list[str] = [
            vertical,
            sub_vertical,
        ]

        county = str(lead.get("County", "")).strip()
        if county:
            tags.append(f"county:{county.lower().replace(' ', '_')}")

        source = str(lead.get("Lead Source", "osint_scraper")).strip()
        if source:
            tags.append(f"source:{source.lower().replace(' ', '_')}")

        lead_score = self._parse_float(lead.get("Lead Score"))
        if lead_score >= 65:
            tags.append("qualified_lead")

        return tags

    @staticmethod
    def _parse_float(value: object) -> float:
        """Safely convert a value to float; return 0.0 on failure."""
        try:
            return float(str(value).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            return 0.0
