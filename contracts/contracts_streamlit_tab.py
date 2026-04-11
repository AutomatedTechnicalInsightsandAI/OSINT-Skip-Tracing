"""
contracts/contracts_streamlit_tab.py
=====================================
Streamlit UI tab for the Contracts & Disputes module.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

from contracts.billing_protection import BillingProtection
from contracts.contract_templates import ContractGenerator
from contracts.dispute_engine import DisputeEngine, DisputeSubmission

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons stored in session state
# ---------------------------------------------------------------------------

_ENGINE_KEY = "_dispute_engine"
_BILLING_KEY = "_billing_protection"


def _get_engine() -> DisputeEngine:
    if _ENGINE_KEY not in st.session_state:
        st.session_state[_ENGINE_KEY] = DisputeEngine()
    return st.session_state[_ENGINE_KEY]


def _get_billing() -> BillingProtection:
    if _BILLING_KEY not in st.session_state:
        st.session_state[_BILLING_KEY] = BillingProtection()
    return st.session_state[_BILLING_KEY]


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------


def render_contracts_tab(df: pd.DataFrame) -> None:
    """
    Render the full Contracts & Disputes UI inside the calling Streamlit page.

    Parameters
    ----------
    df:
        The leads DataFrame from the main app (may be empty).
    """
    st.header("📄 Contracts & Disputes")
    st.caption(
        "⚠️ Documents generated here are templates for internal business use "
        "only and do not constitute legal advice."
    )

    tab_contract, tab_dispute, tab_invoice = st.tabs(
        ["📝 Generate Contract", "⚖️ Dispute Management", "🧾 Invoice Generator"]
    )

    with tab_contract:
        _render_contract_tab()

    with tab_dispute:
        _render_dispute_tab()

    with tab_invoice:
        _render_invoice_tab(df)


# ---------------------------------------------------------------------------
# Sub-tab: Generate Contract
# ---------------------------------------------------------------------------


def _render_contract_tab() -> None:
    st.subheader("Generate MSA + Addendum")

    with st.form("contract_form"):
        col1, col2 = st.columns(2)
        with col1:
            company_name = st.text_input("Company Name", placeholder="Acme Lending LLC")
            contact_name = st.text_input("Contact Name", placeholder="Jane Smith")
            email = st.text_input("Email", placeholder="jane@acmelending.com")
        with col2:
            address = st.text_input("Address", placeholder="123 Main St, Tampa FL 33601")
            state = st.text_input("State", value="Florida")
            monthly_budget = st.number_input(
                "Monthly Budget (USD)", min_value=0.0, value=5000.0, step=500.0
            )

        vertical = st.selectbox(
            "Vertical",
            options=["home_services", "real_estate", "b2b"],
            format_func=lambda v: v.replace("_", " ").title(),
        )

        sub_vertical_options = {
            "home_services": [
                "roofing", "roofing_insurance_claim", "hvac",
                "plumbing", "electrical", "general_home_services",
            ],
            "real_estate": [
                "bridge_loan", "hard_money", "dscr",
                "fix_and_flip", "commercial_mortgage", "residential_purchase",
            ],
            "b2b": [
                "commercial_lender", "mortgage_broker", "real_estate_attorney",
                "title_company", "general_b2b",
            ],
        }
        sub_vertical = st.selectbox(
            "Sub-Vertical",
            options=sub_vertical_options.get(vertical, []),
            format_func=lambda v: v.replace("_", " ").title(),
        )

        submitted = st.form_submit_button(
            "Generate MSA + Addendum", type="primary", use_container_width=True
        )

    if submitted:
        buyer_info = {
            "company_name": company_name,
            "contact_name": contact_name,
            "email": email,
            "address": address,
            "state": state,
            "monthly_budget": monthly_budget,
        }
        gen = ContractGenerator()
        msa = gen.generate_msa(buyer_info, vertical)
        addendum = gen.generate_vertical_addendum(vertical, sub_vertical, buyer_info)
        full_contract = msa + "\n\n---\n\n" + addendum

        st.success("✅ Contract generated!")
        st.markdown(full_contract)

        st.download_button(
            label="⬇️ Download Contract (Markdown)",
            data=full_contract.encode("utf-8"),
            file_name=f"contract_{company_name.replace(' ', '_')}.md",
            mime="text/markdown",
        )
        st.download_button(
            label="⬇️ Download Contract (TXT)",
            data=full_contract.encode("utf-8"),
            file_name=f"contract_{company_name.replace(' ', '_')}.txt",
            mime="text/plain",
        )


# ---------------------------------------------------------------------------
# Sub-tab: Dispute Management
# ---------------------------------------------------------------------------


def _render_dispute_tab() -> None:
    st.subheader("Submit & Evaluate a Dispute")

    engine = _get_engine()

    with st.form("dispute_form"):
        col1, col2 = st.columns(2)
        with col1:
            lead_id = st.text_input("Lead ID", placeholder="LEAD-001")
            buyer_id = st.text_input("Buyer ID", placeholder="BUYER-42")
            buyer_email = st.text_input("Buyer Email", placeholder="buyer@example.com")
        with col2:
            reason = st.selectbox(
                "Dispute Reason",
                options=[
                    "wrong_number",
                    "not_qualified",
                    "duplicate",
                    "fake_lead",
                    "outside_territory",
                ],
                format_func=lambda r: r.replace("_", " ").title(),
            )
            delivered_at = st.date_input(
                "Lead Delivered At (date)",
                value=datetime.now(timezone.utc).date() - timedelta(days=1),
            )
            delivered_time = st.time_input(
                "Lead Delivered At (time, UTC)",
                value=datetime.now(timezone.utc).time(),
            )

        evidence = st.text_area(
            "Evidence / Notes (optional)",
            placeholder=(
                "For outside_territory disputes, enter the lead's zip code here."
            ),
        )

        evaluate = st.form_submit_button(
            "Submit & Evaluate Dispute", type="primary", use_container_width=True
        )

    if evaluate:
        delivered_dt = datetime.combine(delivered_at, delivered_time).replace(
            tzinfo=timezone.utc
        )
        submission = DisputeSubmission(
            lead_id=lead_id,
            buyer_id=buyer_id,
            buyer_email=buyer_email,
            dispute_reason=reason,
            submitted_at=datetime.now(timezone.utc),
            lead_delivered_at=delivered_dt,
            evidence=evidence if evidence else None,
        )
        decision = engine.evaluate_dispute(submission)

        # Store dispute history in session state
        history_key = "_dispute_history"
        if history_key not in st.session_state:
            st.session_state[history_key] = []
        st.session_state[history_key].append(
            {
                "lead_id": decision.lead_id,
                "decision": decision.decision,
                "reason": decision.reason,
                "credit_amount": decision.credit_amount,
                "processed_at": decision.processed_at.strftime("%Y-%m-%d %H:%M UTC"),
                "reviewer": decision.reviewer,
            }
        )

        # Decision card
        if decision.decision == "auto_approved":
            st.success(f"✅ **Auto-Approved** — Credit: ${decision.credit_amount:.2f}")
        elif decision.decision == "auto_denied":
            st.error("❌ **Auto-Denied**")
        else:
            st.warning("🔍 **Manual Review Required**")

        col_a, col_b = st.columns(2)
        col_a.metric("Decision", decision.decision.replace("_", " ").title())
        col_b.metric("Credit Amount", f"${decision.credit_amount:.2f}")
        st.info(f"**Reason:** {decision.reason}")

        if decision.decision == "auto_approved":
            st.caption(
                "Credit will be applied to the next invoice. "
                "A replacement lead will be issued within 10 business days."
            )
        elif decision.decision == "manual_review":
            st.caption(
                "Our QA team will review this dispute within 5 business days "
                "and contact you at the e-mail on file."
            )

    # Recent dispute history table
    history_key = "_dispute_history"
    if history_key in st.session_state and st.session_state[history_key]:
        st.divider()
        st.subheader("Recent Dispute History (last 20)")
        history_df = pd.DataFrame(
            st.session_state[history_key][-20:][::-1]
        )
        st.dataframe(history_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Sub-tab: Invoice Generator
# ---------------------------------------------------------------------------


def _render_invoice_tab(df: pd.DataFrame) -> None:
    st.subheader("Generate Invoice")

    billing = _get_billing()

    col1, col2, col3 = st.columns(3)
    with col1:
        buyer_id = st.text_input("Buyer ID", placeholder="BUYER-42", key="inv_buyer_id")
    with col2:
        start_date = st.date_input(
            "Period Start",
            value=(datetime.now(timezone.utc) - timedelta(days=30)).date(),
            key="inv_start",
        )
    with col3:
        end_date = st.date_input(
            "Period End",
            value=datetime.now(timezone.utc).date(),
            key="inv_end",
        )

    # Build deliveries from the leads dataframe if available
    deliveries: list[dict] = []
    if not df.empty:
        st.info(
            f"ℹ️ {len(df)} lead(s) from the current session will be included "
            "as line items."
        )
        for _, row in df.iterrows():
            deliveries.append(
                {
                    "lead_id": str(row.get("Lead ID", row.name)),
                    "lead_type": str(row.get("Lead Type", row.get("lead_type", "—"))),
                    "delivered_at": datetime.now(timezone.utc),
                    "amount": float(row.get("amount", 0.0)),
                }
            )

    generate_inv = st.button(
        "Generate Invoice", type="primary", use_container_width=False
    )

    if generate_inv:
        period_start = datetime(
            start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc
        )
        period_end = datetime(
            end_date.year, end_date.month, end_date.day, 23, 59, 59,
            tzinfo=timezone.utc,
        )

        # Register a minimal buyer record if not already registered
        if buyer_id not in billing._buyers:
            billing.register_buyer(
                buyer_id=buyer_id,
                buyer_info={"company_name": buyer_id},
                payment_method="card_on_file",
            )

        invoice = billing.generate_invoice(
            buyer_id=buyer_id,
            period_start=period_start,
            period_end=period_end,
            deliveries=deliveries,
        )

        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Subtotal", f"${invoice['subtotal']:.2f}")
        m2.metric("Credits Applied", f"${invoice['credits_applied']:.2f}")
        m3.metric("Total Due", f"${invoice['total_due']:.2f}")

        # Invoice display
        st.divider()
        st.markdown(f"### Invoice `{invoice['invoice_number']}`")
        st.markdown(
            f"**Period:** {invoice['period']}  \n"
            f"**Due Date:** {invoice['due_date']}  \n"
            f"**Payment Status:** {invoice['payment_status'].title()}"
        )

        if invoice["line_items"]:
            st.dataframe(
                pd.DataFrame(invoice["line_items"]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No line items for this period.")

        # Download
        invoice_json = json.dumps(invoice, indent=2, default=str)
        st.download_button(
            label="⬇️ Download Invoice (JSON)",
            data=invoice_json.encode("utf-8"),
            file_name=f"{invoice['invoice_number']}.json",
            mime="application/json",
        )
