"""
contracts/billing_protection.py
================================
Pre-charge validation, invoice generation, and volume-discount calculation
for the Pay-Per-Qualified-Lead platform.

DISCLAIMER: This module is for internal business tooling only and does not
constitute legal or financial advice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Volume discount tiers
# ---------------------------------------------------------------------------

VOLUME_DISCOUNT_TIERS: List[Tuple[int, float]] = [
    (1000, 0.32),
    (500, 0.22),
    (250, 0.11),
    (100, 0.00),
    (0, 0.00),
]


# ---------------------------------------------------------------------------
# BillingProtection
# ---------------------------------------------------------------------------


class BillingProtection:
    """
    Pre-charge validation, invoice generation, and volume-discount helpers.

    State is held in-memory. Integrate with a persistent store by overriding
    ``_load_buyer`` and ``_save_buyer``.
    """

    def __init__(self) -> None:
        # buyers: maps buyer_id -> buyer config dict
        self._buyers: Dict[str, dict] = {}
        # delivery_history: maps buyer_id -> list of delivery dicts
        #   each delivery dict: {lead_id, phone, email, delivered_at (datetime), amount}
        self._delivery_history: Dict[str, List[dict]] = {}
        # credits: maps buyer_id -> pending credit balance
        self._credits: Dict[str, float] = {}

    # -----------------------------------------------------------------------
    # Buyer management helpers
    # -----------------------------------------------------------------------

    def register_buyer(
        self,
        buyer_id: str,
        buyer_info: dict,
        payment_method: Optional[str] = None,
        monthly_cap: Optional[int] = None,
        paused: bool = False,
    ) -> None:
        """Register or update a buyer's account configuration."""
        self._buyers[buyer_id] = {
            "info": buyer_info,
            "payment_method": payment_method,
            "monthly_cap": monthly_cap,
            "paused": paused,
        }
        self._delivery_history.setdefault(buyer_id, [])
        self._credits.setdefault(buyer_id, 0.0)

    def add_credit(self, buyer_id: str, amount: float) -> None:
        """Add a credit balance for a buyer (e.g., from an approved dispute)."""
        self._credits[buyer_id] = self._credits.get(buyer_id, 0.0) + amount

    def record_delivery(self, buyer_id: str, delivery: dict) -> None:
        """Record a completed lead delivery for billing and deduplication."""
        self._delivery_history.setdefault(buyer_id, []).append(delivery)

    # -----------------------------------------------------------------------
    # Core methods
    # -----------------------------------------------------------------------

    def validate_before_charge(
        self, lead_data: dict, buyer_id: str
    ) -> Tuple[bool, str]:
        """
        Run pre-charge validation checks.

        Checks (in order):
        1. Buyer has a valid payment method on file.
        2. Buyer account is not paused.
        3. Lead is not a duplicate (same phone or email in last 30 days).
        4. Buyer has not exceeded their monthly cap (if set).

        Parameters
        ----------
        lead_data:
            Dict with at least ``phone`` and ``email`` keys.
        buyer_id:
            Unique identifier of the buyer account.

        Returns
        -------
        Tuple[bool, str]
            ``(True, "ok")`` if all checks pass, else ``(False, reason)``.
        """
        buyer = self._buyers.get(buyer_id)
        if buyer is None:
            return False, f"Buyer '{buyer_id}' not found in system."

        # Check 1 — payment method
        if not buyer.get("payment_method"):
            return False, "No valid payment method on file for buyer."

        # Check 2 — account paused
        if buyer.get("paused"):
            return False, "Buyer account is currently paused."

        # Check 3 — duplicate check (last 30 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        phone = (lead_data.get("phone") or "").strip()
        email = (lead_data.get("email") or "").strip().lower()
        for delivery in self._delivery_history.get(buyer_id, []):
            delivered_at = delivery.get("delivered_at")
            if isinstance(delivered_at, datetime):
                if delivered_at.tzinfo is None:
                    delivered_at = delivered_at.replace(tzinfo=timezone.utc)
                if delivered_at < cutoff:
                    continue
            d_phone = (delivery.get("phone") or "").strip()
            d_email = (delivery.get("email") or "").strip().lower()
            if phone and d_phone and d_phone == phone:
                return (
                    False,
                    f"Duplicate lead: phone {phone} already delivered to "
                    f"buyer {buyer_id} within the last 30 days.",
                )
            if email and d_email and d_email == email:
                return (
                    False,
                    f"Duplicate lead: email {email} already delivered to "
                    f"buyer {buyer_id} within the last 30 days.",
                )

        # Check 4 — monthly cap
        monthly_cap = buyer.get("monthly_cap")
        if monthly_cap is not None:
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            count_this_month = sum(
                1
                for d in self._delivery_history.get(buyer_id, [])
                if isinstance(d.get("delivered_at"), datetime)
                and d["delivered_at"].replace(tzinfo=timezone.utc)
                >= month_start
            )
            if count_this_month >= monthly_cap:
                return (
                    False,
                    f"Monthly cap of {monthly_cap} leads reached for buyer "
                    f"{buyer_id}.",
                )

        return True, "ok"

    def generate_invoice(
        self,
        buyer_id: str,
        period_start: datetime,
        period_end: datetime,
        deliveries: List[dict],
    ) -> dict:
        """
        Generate a structured invoice dict for a buyer.

        Parameters
        ----------
        buyer_id:
            Unique identifier of the buyer.
        period_start:
            Start of the invoice period (inclusive).
        period_end:
            End of the invoice period (inclusive).
        deliveries:
            List of delivery dicts, each with keys:
            ``lead_id``, ``lead_type``, ``delivered_at``, ``amount``.

        Returns
        -------
        dict
            Structured invoice with line items, totals, credits, and due date.
        """
        buyer = self._buyers.get(buyer_id, {})
        buyer_info = buyer.get("info", {"company_name": buyer_id})

        period_label = (
            f"{period_start.strftime('%Y-%m-%d')} to "
            f"{period_end.strftime('%Y-%m-%d')}"
        )
        invoice_month = period_start.strftime("%Y%m")
        invoice_number = f"INV-{buyer_id}-{invoice_month}"

        line_items = [
            {
                "lead_id": d.get("lead_id", ""),
                "lead_type": d.get("lead_type", ""),
                "delivered_at": (
                    d["delivered_at"].isoformat()
                    if isinstance(d.get("delivered_at"), datetime)
                    else str(d.get("delivered_at", ""))
                ),
                "amount": float(d.get("amount", 0.0)),
            }
            for d in deliveries
        ]

        subtotal = round(sum(item["amount"] for item in line_items), 2)
        credits_applied = round(min(self._credits.get(buyer_id, 0.0), subtotal), 2)
        total_due = round(max(subtotal - credits_applied, 0.0), 2)

        # Deduct applied credits
        if credits_applied > 0:
            self._credits[buyer_id] = round(
                self._credits.get(buyer_id, 0.0) - credits_applied, 2
            )

        due_date = (period_end + timedelta(days=15)).strftime("%Y-%m-%d")

        return {
            "invoice_number": invoice_number,
            "buyer_info": buyer_info,
            "period": period_label,
            "line_items": line_items,
            "subtotal": subtotal,
            "credits_applied": credits_applied,
            "total_due": total_due,
            "due_date": due_date,
            "payment_status": "pending",
        }

    @staticmethod
    def calculate_volume_discount(total_leads: int, vertical: str) -> float:
        """
        Calculate the applicable volume discount rate for a given monthly
        lead count.

        Parameters
        ----------
        total_leads:
            Total leads delivered in the billing period.
        vertical:
            Vertical identifier (currently uniform tiers across verticals).

        Returns
        -------
        float
            Discount rate as a decimal (e.g., 0.11 = 11% discount).
        """
        for threshold, rate in VOLUME_DISCOUNT_TIERS:
            if total_leads >= threshold:
                return rate
        return 0.0
