"""
tests/test_contracts.py
========================
Unit tests for the contracts/ module.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from contracts.billing_protection import BillingProtection
from contracts.contract_templates import ContractGenerator
from contracts.dispute_engine import DisputeEngine, DisputeSubmission


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BUYER_INFO = {
    "company_name": "Acme Lending LLC",
    "contact_name": "Jane Smith",
    "address": "123 Main St, Tampa FL 33601",
    "email": "jane@acmelending.com",
    "state": "Florida",
}


@pytest.fixture()
def generator() -> ContractGenerator:
    return ContractGenerator()


@pytest.fixture()
def engine() -> DisputeEngine:
    return DisputeEngine()


@pytest.fixture()
def billing() -> BillingProtection:
    bp = BillingProtection()
    bp.register_buyer(
        buyer_id="BUYER-42",
        buyer_info=BUYER_INFO,
        payment_method="pm_test_card",
        monthly_cap=500,
    )
    return bp


# ---------------------------------------------------------------------------
# ContractGenerator.generate_msa — section presence
# ---------------------------------------------------------------------------

MSA_REQUIRED_SECTIONS = [
    "## 1. Parties",
    "## 2. Services Description",
    "## 3. Lead Qualification Standards",
    "## 4. Pricing and Payment Terms",
    "## 5. Lead Delivery Process",
    "## 6. Exclusivity Terms",
    "## 7. Dispute Resolution Procedure",
    "## 8. Refund and Credit Policy",
    "## 9. Lead Replacement Guarantee",
    "## 10. Confidentiality",
    "## 11. Term and Termination",
    "## 12. Limitation of Liability",
    "## 13. Governing Law",
    "## 14. Signatures",
]


@pytest.mark.parametrize("section", MSA_REQUIRED_SECTIONS)
def test_msa_contains_all_required_sections(generator, section):
    msa = generator.generate_msa(BUYER_INFO, "real_estate")
    assert section in msa, f"MSA is missing section: {section}"


def test_msa_contains_buyer_company_name(generator):
    msa = generator.generate_msa(BUYER_INFO, "real_estate")
    assert BUYER_INFO["company_name"] in msa


def test_msa_contains_governing_law_florida(generator):
    msa = generator.generate_msa(BUYER_INFO, "home_services")
    assert "Florida" in msa


# ---------------------------------------------------------------------------
# ContractGenerator.generate_vertical_addendum — sub-vertical pricing
# ---------------------------------------------------------------------------


def test_addendum_contains_sub_vertical_pricing(generator):
    addendum = generator.generate_vertical_addendum(
        "real_estate", "bridge_loan", BUYER_INFO
    )
    assert "250.00" in addendum  # bridge loan price


def test_addendum_contains_roofing_insurance_special_terms(generator):
    addendum = generator.generate_vertical_addendum(
        "home_services", "roofing_insurance_claim", BUYER_INFO
    )
    assert "120.00" in addendum
    assert "insurance" in addendum.lower()


def test_addendum_contains_volume_discount_table(generator):
    addendum = generator.generate_vertical_addendum(
        "b2b", "commercial_lender", BUYER_INFO
    )
    assert "32%" in addendum  # top-tier discount


# ---------------------------------------------------------------------------
# DisputeEngine.evaluate_dispute — auto-approval for duplicate
# ---------------------------------------------------------------------------


def test_dispute_auto_approved_duplicate(engine):
    engine.register_delivery("LEAD-DUP", "BUYER-42", price=250.00)
    engine.register_delivery("LEAD-DUP", "BUYER-42", price=250.00)

    now = datetime.now(timezone.utc)
    submission = DisputeSubmission(
        lead_id="LEAD-DUP",
        buyer_id="BUYER-42",
        buyer_email="buyer@example.com",
        dispute_reason="duplicate",
        submitted_at=now,
        lead_delivered_at=now - timedelta(hours=12),
    )
    decision = engine.evaluate_dispute(submission)
    assert decision.decision == "auto_approved"
    assert decision.credit_amount == 250.00


# ---------------------------------------------------------------------------
# DisputeEngine.evaluate_dispute — auto-denial outside 72-hour window
# ---------------------------------------------------------------------------


def test_dispute_auto_denied_outside_window(engine):
    engine.register_delivery("LEAD-OLD", "BUYER-42", price=85.00)

    now = datetime.now(timezone.utc)
    submission = DisputeSubmission(
        lead_id="LEAD-OLD",
        buyer_id="BUYER-42",
        buyer_email="buyer@example.com",
        dispute_reason="wrong_number",
        submitted_at=now,
        lead_delivered_at=now - timedelta(hours=73),  # > 72 h
    )
    decision = engine.evaluate_dispute(submission)
    assert decision.decision == "auto_denied"
    assert decision.credit_amount == 0.0
    assert "72" in decision.reason


# ---------------------------------------------------------------------------
# DisputeEngine.evaluate_dispute — auto-approval for wrong_number (short call)
# ---------------------------------------------------------------------------


def test_dispute_auto_approved_wrong_number_short_call(engine):
    engine.register_delivery("LEAD-WN", "BUYER-42", price=65.00)
    engine.register_call_duration("LEAD-WN", duration_seconds=10)

    now = datetime.now(timezone.utc)
    submission = DisputeSubmission(
        lead_id="LEAD-WN",
        buyer_id="BUYER-42",
        buyer_email="buyer@example.com",
        dispute_reason="wrong_number",
        submitted_at=now,
        lead_delivered_at=now - timedelta(hours=1),
    )
    decision = engine.evaluate_dispute(submission)
    assert decision.decision == "auto_approved"
    assert decision.credit_amount == 65.00


def test_dispute_manual_review_wrong_number_long_call(engine):
    engine.register_delivery("LEAD-WN2", "BUYER-42", price=65.00)
    engine.register_call_duration("LEAD-WN2", duration_seconds=120)

    now = datetime.now(timezone.utc)
    submission = DisputeSubmission(
        lead_id="LEAD-WN2",
        buyer_id="BUYER-42",
        buyer_email="buyer@example.com",
        dispute_reason="wrong_number",
        submitted_at=now,
        lead_delivered_at=now - timedelta(hours=1),
    )
    decision = engine.evaluate_dispute(submission)
    assert decision.decision == "manual_review"


# ---------------------------------------------------------------------------
# BillingProtection.generate_invoice — correct totals
# ---------------------------------------------------------------------------


def test_invoice_generation_correct_totals(billing):
    deliveries = [
        {
            "lead_id": "L1",
            "lead_type": "Bridge Loan",
            "delivered_at": datetime(2024, 1, 10, tzinfo=timezone.utc),
            "amount": 250.00,
        },
        {
            "lead_id": "L2",
            "lead_type": "Hard Money",
            "delivered_at": datetime(2024, 1, 15, tzinfo=timezone.utc),
            "amount": 275.00,
        },
    ]
    invoice = billing.generate_invoice(
        buyer_id="BUYER-42",
        period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
        deliveries=deliveries,
    )
    assert invoice["subtotal"] == 525.00
    assert invoice["total_due"] == 525.00
    assert invoice["credits_applied"] == 0.00
    assert invoice["invoice_number"] == "INV-BUYER-42-202401"


def test_invoice_credits_applied(billing):
    billing.add_credit("BUYER-42", 100.00)
    deliveries = [
        {
            "lead_id": "L3",
            "lead_type": "DSCR",
            "delivered_at": datetime(2024, 2, 5, tzinfo=timezone.utc),
            "amount": 225.00,
        }
    ]
    invoice = billing.generate_invoice(
        buyer_id="BUYER-42",
        period_start=datetime(2024, 2, 1, tzinfo=timezone.utc),
        period_end=datetime(2024, 2, 28, tzinfo=timezone.utc),
        deliveries=deliveries,
    )
    assert invoice["credits_applied"] == 100.00
    assert invoice["total_due"] == 125.00


# ---------------------------------------------------------------------------
# BillingProtection.calculate_volume_discount — tier thresholds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "total_leads, expected_rate",
    [
        (50, 0.00),   # below 100 — 0% per spec (Silver tier starts at 100 but also 0%)
        (100, 0.00),  # exactly 100 — Silver tier, 0% discount per spec
        (250, 0.11),  # Gold tier threshold
        (499, 0.11),  # just below 500
        (500, 0.22),  # 500 threshold
        (999, 0.22),  # just below 1000
        (1000, 0.32), # 1000 threshold
        (1500, 0.32), # above 1000
    ],
)
def test_volume_discount_tiers(total_leads, expected_rate):
    rate = BillingProtection.calculate_volume_discount(total_leads, "real_estate")
    assert rate == expected_rate, (
        f"Expected {expected_rate} for {total_leads} leads, got {rate}"
    )


# ---------------------------------------------------------------------------
# BillingProtection.validate_before_charge — blocks duplicate leads
# ---------------------------------------------------------------------------


def test_billing_validation_blocks_duplicate_phone(billing):
    now = datetime.now(timezone.utc)
    billing.record_delivery(
        "BUYER-42",
        {
            "lead_id": "L-ORIG",
            "phone": "555-999-8888",
            "email": "orig@example.com",
            "delivered_at": now - timedelta(days=5),
            "amount": 85.00,
        },
    )
    ok, reason = billing.validate_before_charge(
        lead_data={"phone": "555-999-8888", "email": "new@example.com"},
        buyer_id="BUYER-42",
    )
    assert ok is False
    assert "Duplicate" in reason


def test_billing_validation_blocks_duplicate_email(billing):
    now = datetime.now(timezone.utc)
    billing.record_delivery(
        "BUYER-42",
        {
            "lead_id": "L-ORIG2",
            "phone": "555-000-1111",
            "email": "dup@example.com",
            "delivered_at": now - timedelta(days=3),
            "amount": 85.00,
        },
    )
    ok, reason = billing.validate_before_charge(
        lead_data={"phone": "555-777-2222", "email": "dup@example.com"},
        buyer_id="BUYER-42",
    )
    assert ok is False
    assert "Duplicate" in reason


def test_billing_validation_passes_for_new_lead(billing):
    ok, reason = billing.validate_before_charge(
        lead_data={"phone": "555-111-2222", "email": "brand_new@example.com"},
        buyer_id="BUYER-42",
    )
    assert ok is True
    assert reason == "ok"


def test_billing_validation_blocks_paused_account():
    bp = BillingProtection()
    bp.register_buyer(
        "PAUSED-BUYER",
        {"company_name": "Paused Co"},
        payment_method="pm_test",
        paused=True,
    )
    ok, reason = bp.validate_before_charge(
        {"phone": "555-000-0000", "email": "a@b.com"}, "PAUSED-BUYER"
    )
    assert ok is False
    assert "paused" in reason.lower()


def test_billing_validation_blocks_missing_payment_method():
    bp = BillingProtection()
    bp.register_buyer("NO-PM", {"company_name": "No Card Co"}, payment_method=None)
    ok, reason = bp.validate_before_charge(
        {"phone": "555-111-3333", "email": "x@y.com"}, "NO-PM"
    )
    assert ok is False
    assert "payment method" in reason.lower()
