"""
contracts/dispute_engine.py
============================
Deterministic dispute evaluation engine for the Pay-Per-Qualified-Lead
platform.

DISCLAIMER: This module provides automated business-logic tooling for
internal lead-credit management. It does not constitute legal advice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISPUTE_WINDOW_HOURS: int = 72
SHORT_CALL_THRESHOLD_SECONDS: int = 30

VALID_DISPUTE_REASONS = frozenset(
    [
        "wrong_number",
        "not_qualified",
        "duplicate",
        "fake_lead",
        "outside_territory",
    ]
)

DECISIONS = frozenset(["auto_approved", "auto_denied", "manual_review"])


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DisputeSubmission:
    """A buyer's request to dispute a delivered lead."""

    lead_id: str
    buyer_id: str
    buyer_email: str
    dispute_reason: str  # one of VALID_DISPUTE_REASONS
    submitted_at: datetime
    lead_delivered_at: datetime
    evidence: Optional[str] = None  # optional free-text notes


@dataclass
class DisputeDecision:
    """The outcome of evaluating a DisputeSubmission."""

    lead_id: str
    decision: str  # one of DECISIONS
    reason: str
    credit_amount: float
    processed_at: datetime
    reviewer: str  # "system" or a human reviewer name


# ---------------------------------------------------------------------------
# DisputeEngine
# ---------------------------------------------------------------------------


class DisputeEngine:
    """
    Evaluates lead dispute submissions and returns deterministic decisions.

    State is held in-memory for simplicity.  Integrate with a persistent
    store (database, file, etc.) by overriding ``_persist_decision``.
    """

    def __init__(self) -> None:
        # delivery_log: maps lead_id -> list of buyer_ids that received the lead
        self._delivery_log: Dict[str, List[str]] = {}
        # call_durations: maps lead_id -> call duration in seconds
        self._call_durations: Dict[str, int] = {}
        # buyer_territories: maps buyer_id -> set of allowed zip codes
        self._buyer_territories: Dict[str, set] = {}
        # lead_prices: maps lead_id -> lead price
        self._lead_prices: Dict[str, float] = {}
        # decision_log: ordered list of all DisputeDecision objects
        self._decision_log: List[DisputeDecision] = []

    # -----------------------------------------------------------------------
    # Configuration helpers (call before evaluate_dispute in production)
    # -----------------------------------------------------------------------

    def register_delivery(
        self, lead_id: str, buyer_id: str, price: float = 0.0
    ) -> None:
        """Record that *lead_id* was delivered to *buyer_id* at *price*."""
        self._delivery_log.setdefault(lead_id, []).append(buyer_id)
        self._lead_prices[lead_id] = price

    def register_call_duration(self, lead_id: str, duration_seconds: int) -> None:
        """Record the call duration (seconds) for a lead."""
        self._call_durations[lead_id] = duration_seconds

    def set_buyer_territory(self, buyer_id: str, zip_codes: set) -> None:
        """Define the set of zip codes that are valid for *buyer_id*."""
        self._buyer_territories[buyer_id] = zip_codes

    # -----------------------------------------------------------------------
    # Core evaluation
    # -----------------------------------------------------------------------

    def evaluate_dispute(self, submission: DisputeSubmission) -> DisputeDecision:
        """
        Apply deterministic rules to a DisputeSubmission and return a
        DisputeDecision.

        Rules (evaluated in order):
        1. Submitted > 72 hours after delivery  → auto_denied
        2. reason == "duplicate" AND lead delivered twice to buyer  → auto_approved
        3. reason == "wrong_number" AND call < 30 s  → auto_approved
        4. reason == "outside_territory" AND zip not in buyer territory  → auto_approved
        5. reason == "not_qualified"  → manual_review
        6. reason == "fake_lead"  → manual_review
        """
        elapsed_hours = (
            submission.submitted_at - submission.lead_delivered_at
        ).total_seconds() / 3600

        lead_price = self._lead_prices.get(submission.lead_id, 0.0)

        decision: DisputeDecision

        # Rule 1 — outside dispute window
        if elapsed_hours > DISPUTE_WINDOW_HOURS:
            decision = DisputeDecision(
                lead_id=submission.lead_id,
                decision="auto_denied",
                reason=(
                    f"Outside dispute window: dispute submitted "
                    f"{elapsed_hours:.1f} h after delivery "
                    f"(limit {DISPUTE_WINDOW_HOURS} h)."
                ),
                credit_amount=0.0,
                processed_at=datetime.now(timezone.utc),
                reviewer="system",
            )

        # Rule 2 — duplicate
        elif submission.dispute_reason == "duplicate":
            deliveries = self._delivery_log.get(submission.lead_id, [])
            buyer_count = deliveries.count(submission.buyer_id)
            if buyer_count >= 2:
                decision = DisputeDecision(
                    lead_id=submission.lead_id,
                    decision="auto_approved",
                    reason=(
                        f"Duplicate confirmed: lead {submission.lead_id} "
                        f"delivered {buyer_count}x to buyer {submission.buyer_id}."
                    ),
                    credit_amount=lead_price,
                    processed_at=datetime.now(timezone.utc),
                    reviewer="system",
                )
            else:
                decision = DisputeDecision(
                    lead_id=submission.lead_id,
                    decision="manual_review",
                    reason=(
                        "Duplicate claimed but delivery log does not confirm "
                        "multiple deliveries to this buyer."
                    ),
                    credit_amount=0.0,
                    processed_at=datetime.now(timezone.utc),
                    reviewer="system",
                )

        # Rule 3 — wrong number with short call
        elif submission.dispute_reason == "wrong_number":
            duration = self._call_durations.get(submission.lead_id)
            if duration is not None and duration < SHORT_CALL_THRESHOLD_SECONDS:
                decision = DisputeDecision(
                    lead_id=submission.lead_id,
                    decision="auto_approved",
                    reason=(
                        f"Wrong number confirmed: call duration {duration} s "
                        f"< {SHORT_CALL_THRESHOLD_SECONDS} s threshold."
                    ),
                    credit_amount=lead_price,
                    processed_at=datetime.now(timezone.utc),
                    reviewer="system",
                )
            else:
                decision = DisputeDecision(
                    lead_id=submission.lead_id,
                    decision="manual_review",
                    reason=(
                        "Wrong number claimed but call duration record is "
                        "unavailable or >= 30 s — requires human verification."
                    ),
                    credit_amount=0.0,
                    processed_at=datetime.now(timezone.utc),
                    reviewer="system",
                )

        # Rule 4 — outside territory
        elif submission.dispute_reason == "outside_territory":
            territory = self._buyer_territories.get(submission.buyer_id)
            lead_zip = (submission.evidence or "").strip()
            if territory is not None and lead_zip not in territory:
                decision = DisputeDecision(
                    lead_id=submission.lead_id,
                    decision="auto_approved",
                    reason=(
                        f"Territory mismatch confirmed: zip '{lead_zip}' is "
                        f"not in buyer {submission.buyer_id}'s territory."
                    ),
                    credit_amount=lead_price,
                    processed_at=datetime.now(timezone.utc),
                    reviewer="system",
                )
            else:
                decision = DisputeDecision(
                    lead_id=submission.lead_id,
                    decision="manual_review",
                    reason=(
                        "Outside-territory claimed but territory config is "
                        "missing or zip code not provided — requires human "
                        "verification."
                    ),
                    credit_amount=0.0,
                    processed_at=datetime.now(timezone.utc),
                    reviewer="system",
                )

        # Rules 5 & 6 — always manual review
        elif submission.dispute_reason in ("not_qualified", "fake_lead"):
            decision = DisputeDecision(
                lead_id=submission.lead_id,
                decision="manual_review",
                reason=(
                    f"Reason '{submission.dispute_reason}' requires human "
                    "verification of lead qualification criteria."
                ),
                credit_amount=0.0,
                processed_at=datetime.now(timezone.utc),
                reviewer="system",
            )

        else:
            decision = DisputeDecision(
                lead_id=submission.lead_id,
                decision="manual_review",
                reason=(
                    f"Unrecognised dispute reason '{submission.dispute_reason}' "
                    "— escalated to manual review."
                ),
                credit_amount=0.0,
                processed_at=datetime.now(timezone.utc),
                reviewer="system",
            )

        self._persist_decision(decision, submission)
        return decision

    # -----------------------------------------------------------------------
    # Reporting
    # -----------------------------------------------------------------------

    def generate_dispute_report(
        self,
        buyer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """
        Return a summary dict for all disputes belonging to *buyer_id*
        processed between *start_date* and *end_date* (inclusive).
        """
        relevant = [
            d
            for d in self._decision_log
            if self._dispute_belongs_to_buyer(d, buyer_id)
            and start_date <= d.processed_at <= end_date
        ]

        total = len(relevant)
        auto_approved = sum(1 for d in relevant if d.decision == "auto_approved")
        manual_review = sum(1 for d in relevant if d.decision == "manual_review")
        denied = sum(1 for d in relevant if d.decision == "auto_denied")
        total_credits = sum(d.credit_amount for d in relevant if d.decision == "auto_approved")

        # dispute rate requires knowledge of total leads delivered; express as
        # a percentage of decisions in scope if total > 0
        all_decisions_count = len(self._decision_log) or 1
        dispute_rate_pct = round((total / all_decisions_count) * 100, 2)

        return {
            "buyer_id": buyer_id,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_disputes": total,
            "auto_approved": auto_approved,
            "manual_review": manual_review,
            "denied": denied,
            "total_credits_issued": round(total_credits, 2),
            "dispute_rate_pct": dispute_rate_pct,
        }

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _persist_decision(
        self, decision: DisputeDecision, submission: DisputeSubmission
    ) -> None:
        """Store a decision and emit a structured log entry."""
        self._decision_log.append(decision)
        logger.info(
            "Dispute decision | lead=%s buyer=%s decision=%s credit=%.2f "
            "reason=%s",
            decision.lead_id,
            submission.buyer_id,
            decision.decision,
            decision.credit_amount,
            decision.reason,
        )

    def _dispute_belongs_to_buyer(
        self, decision: DisputeDecision, buyer_id: str
    ) -> bool:
        """Check whether a logged decision belongs to *buyer_id*.

        The decision log does not store the buyer_id directly; we look it up
        from the delivery log.
        """
        deliveries = self._delivery_log.get(decision.lead_id, [])
        return buyer_id in deliveries
