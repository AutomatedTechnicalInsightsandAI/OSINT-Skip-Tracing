"""
GoHighLevel Automation Triggers
=================================

Defines trigger payload dataclasses and a webhook handler for GHL automations:

- :class:`SpeedToLeadTrigger` — 30-minute follow-up SMS after lead delivery
- :class:`MonthlyReportTrigger` — monthly summary payload per buyer
- :class:`DisputeTrigger` — dispute auto-approval within a 72-hour window
- :func:`handle_lead_delivery_webhook` — validates HMAC signature and routes
  an inbound webhook POST body to the correct trigger

Usage::

    from ghl.automation_triggers import handle_lead_delivery_webhook

    result = handle_lead_delivery_webhook(
        body=request.json(),
        signature_header=request.headers.get("X-GHL-Signature", ""),
    )
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_WEBHOOK_SECRET = os.getenv("GHL_WEBHOOK_SECRET", "")


# ---------------------------------------------------------------------------
# SpeedToLeadTrigger
# ---------------------------------------------------------------------------


@dataclass
class SpeedToLeadTrigger:
    """Trigger payload for a 30-minute speed-to-lead SMS follow-up.

    Attributes
    ----------
    buyer_id:
        Internal buyer / agent identifier.
    contact_id:
        GHL contact ID of the newly delivered lead.
    phone:
        Destination phone number in E.164 format.
    delivered_at:
        ISO-8601 UTC timestamp when the lead was delivered.
    """

    buyer_id: str
    contact_id: str
    phone: str
    delivered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def build_sms_payload(self) -> dict:
        """Build the GHL SMS automation payload for a 30-min follow-up.

        Returns
        -------
        dict
            Payload dict ready to POST to the GHL conversations/messages API.
        """
        message = (
            "Hi! This is Prime Coastal Funding. We just matched you with a new "
            "qualified lead. Reply YES to get the details, or call us at any time."
        )
        return {
            "type": "SMS",
            "contactId": self.contact_id,
            "message": message,
            "scheduledAt": self.delivered_at,
            "meta": {
                "buyerId": self.buyer_id,
                "triggerType": "speed_to_lead_30min",
            },
        }


# ---------------------------------------------------------------------------
# MonthlyReportTrigger
# ---------------------------------------------------------------------------


@dataclass
class MonthlyReportTrigger:
    """Trigger payload for a monthly lead-delivery summary email.

    Attributes
    ----------
    buyer_id:
        Internal buyer / agent identifier.
    contact_id:
        GHL contact ID of the buyer receiving the report.
    report_month:
        Year-month string, e.g. ``"2024-03"``.
    leads_delivered:
        Total leads delivered this month.
    leads_qualified:
        Number of qualified leads (score ≥ 65) delivered.
    total_pipeline_value:
        Sum of opportunity values for the month.
    """

    buyer_id: str
    contact_id: str
    report_month: str
    leads_delivered: int = 0
    leads_qualified: int = 0
    total_pipeline_value: float = 0.0

    def build_email_payload(self) -> dict:
        """Build the GHL email automation payload for the monthly report.

        Returns
        -------
        dict
            Payload dict ready to POST to the GHL conversations/messages API.
        """
        subject = f"Your Prime Coastal Funding Lead Report — {self.report_month}"
        body = (
            f"<h2>Monthly Lead Summary — {self.report_month}</h2>"
            f"<p><strong>Leads Delivered:</strong> {self.leads_delivered}</p>"
            f"<p><strong>Qualified Leads:</strong> {self.leads_qualified}</p>"
            f"<p><strong>Total Pipeline Value:</strong> "
            f"${self.total_pipeline_value:,.2f}</p>"
            "<p>Log in to your dashboard to review each lead in detail.</p>"
        )
        return {
            "type": "Email",
            "contactId": self.contact_id,
            "subject": subject,
            "body": body,
            "meta": {
                "buyerId": self.buyer_id,
                "triggerType": "monthly_report",
                "reportMonth": self.report_month,
            },
        }


# ---------------------------------------------------------------------------
# DisputeTrigger
# ---------------------------------------------------------------------------


@dataclass
class DisputeTrigger:
    """Trigger payload for a lead-quality dispute.

    Attributes
    ----------
    dispute_id:
        Unique identifier for the dispute.
    contact_id:
        GHL contact ID of the disputed lead.
    buyer_id:
        Internal buyer identifier who raised the dispute.
    disputed_at:
        ISO-8601 UTC timestamp when the dispute was raised.
    reason:
        Free-text reason supplied by the buyer.
    """

    dispute_id: str
    contact_id: str
    buyer_id: str
    disputed_at: str
    reason: str = ""

    @property
    def auto_approve(self) -> bool:
        """Return True if the dispute was raised within the 72-hour window.

        Returns
        -------
        bool
            True when the dispute timestamp is within 72 hours of now.
        """
        try:
            disputed_dt = datetime.fromisoformat(self.disputed_at)
            if disputed_dt.tzinfo is None:
                disputed_dt = disputed_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta_hours = (now - disputed_dt).total_seconds() / 3600
            return delta_hours <= 72
        except (ValueError, TypeError):
            logger.warning(
                "DisputeTrigger: could not parse disputed_at=%s", self.disputed_at
            )
            return False


# ---------------------------------------------------------------------------
# LeadDeliveryWebhook
# ---------------------------------------------------------------------------


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify the HMAC-SHA256 signature of an inbound GHL webhook.

    Parameters
    ----------
    body:
        Raw request body bytes.
    signature:
        Value of the ``X-GHL-Signature`` header.
    secret:
        Shared webhook secret.

    Returns
    -------
    bool
        True when the computed digest matches ``signature``.
    """
    if not secret:
        logger.warning(
            "GHL_WEBHOOK_SECRET is not set — skipping signature verification."
        )
        return True
    expected = hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def handle_lead_delivery_webhook(
    body: dict,
    signature_header: str = "",
    raw_body: bytes | None = None,
) -> dict:
    """Validate and route an inbound GHL lead-delivery webhook.

    This is a plain function (not a FastAPI route) so it can be imported and
    called from any web framework or test harness.

    Parameters
    ----------
    body:
        Parsed JSON body of the webhook POST request.
    signature_header:
        Value of the ``X-GHL-Signature`` HTTP header.
    raw_body:
        Raw bytes of the request body used for HMAC verification.  If
        omitted, signature verification is skipped.

    Returns
    -------
    dict
        A response dict with ``{"status": "ok", "trigger": <type>}`` on
        success, or ``{"status": "error", "detail": <message>}`` on failure.
    """
    # Signature verification
    if raw_body is not None:
        if not _verify_signature(raw_body, signature_header, _WEBHOOK_SECRET):
            logger.error("GHL webhook signature mismatch")
            return {"status": "error", "detail": "invalid_signature"}

    event_type = body.get("type", "")
    logger.info("GHL webhook received | type=%s", event_type)

    if event_type == "lead_delivered":
        delivered_at = body.get("deliveredAt")
        if not delivered_at:
            delivered_at = datetime.now(timezone.utc).isoformat()
            logger.warning(
                "GHL webhook lead_delivered missing 'deliveredAt'; "
                "using current time as fallback."
            )
        trigger = SpeedToLeadTrigger(
            buyer_id=body.get("buyerId", ""),
            contact_id=body.get("contactId", ""),
            phone=body.get("phone", ""),
            delivered_at=delivered_at,
        )
        payload = trigger.build_sms_payload()
        logger.debug("SpeedToLeadTrigger payload: %s", payload)
        return {"status": "ok", "trigger": "speed_to_lead", "payload": payload}

    if event_type == "monthly_report":
        trigger = MonthlyReportTrigger(
            buyer_id=body.get("buyerId", ""),
            contact_id=body.get("contactId", ""),
            report_month=body.get("reportMonth", ""),
            leads_delivered=body.get("leadsDelivered", 0),
            leads_qualified=body.get("leadsQualified", 0),
            total_pipeline_value=body.get("totalPipelineValue", 0.0),
        )
        payload = trigger.build_email_payload()
        logger.debug("MonthlyReportTrigger payload: %s", payload)
        return {"status": "ok", "trigger": "monthly_report", "payload": payload}

    if event_type == "dispute":
        trigger = DisputeTrigger(
            dispute_id=body.get("disputeId", ""),
            contact_id=body.get("contactId", ""),
            buyer_id=body.get("buyerId", ""),
            disputed_at=body.get("disputedAt", ""),
            reason=body.get("reason", ""),
        )
        logger.info(
            "DisputeTrigger | id=%s auto_approve=%s",
            trigger.dispute_id,
            trigger.auto_approve,
        )
        return {
            "status": "ok",
            "trigger": "dispute",
            "auto_approve": trigger.auto_approve,
            "dispute_id": trigger.dispute_id,
        }

    logger.warning("Unknown GHL webhook event type: %s", event_type)
    return {"status": "error", "detail": f"unknown_event_type:{event_type}"}
