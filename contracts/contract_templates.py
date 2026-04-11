"""
contracts/contract_templates.py
================================
Generates legally-structured plain-text / Markdown contract documents for
the Pay-Per-Qualified-Lead platform.

DISCLAIMER: The documents produced by this module are templates for internal
business use only and do NOT constitute legal advice.  Have a licensed
attorney review all agreements before execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

# ---------------------------------------------------------------------------
# Pricing tables (per vertical / sub-vertical)
# ---------------------------------------------------------------------------

PRICING: Dict[str, Dict[str, float]] = {
    "home_services": {
        "roofing": 85.00,
        "roofing_insurance_claim": 120.00,
        "hvac": 65.00,
        "plumbing": 55.00,
        "electrical": 60.00,
        "general_home_services": 45.00,
    },
    "real_estate": {
        "bridge_loan": 250.00,
        "hard_money": 275.00,
        "dscr": 225.00,
        "fix_and_flip": 200.00,
        "commercial_mortgage": 300.00,
        "residential_purchase": 175.00,
    },
    "b2b": {
        "commercial_lender": 350.00,
        "mortgage_broker": 300.00,
        "real_estate_attorney": 275.00,
        "title_company": 250.00,
        "general_b2b": 200.00,
    },
}

# ---------------------------------------------------------------------------
# Qualification criteria (per vertical)
# ---------------------------------------------------------------------------

QUALIFICATION_CRITERIA: Dict[str, str] = {
    "home_services": (
        "1. Homeowner identity confirmed (name matches public records).\n"
        "2. Active project timeline stated: within 90 days.\n"
        "3. Minimum inbound call duration: 90 seconds.\n"
        "4. Property located within Buyer's defined geographic territory.\n"
        "5. No prior contact with Buyer in last 180 days (deduplication check).\n"
        "6. Insurance claim leads (roofing): claim number on file or adjuster "
        "   visit scheduled."
    ),
    "real_estate": (
        "1. Deal identified: subject property address provided.\n"
        "2. Funds verified: borrower has stated available down payment / equity.\n"
        "3. Stated loan timeline: closing target within 120 days.\n"
        "4. Minimum credit profile indicated (as appropriate for product).\n"
        "5. No prior contact with Buyer in last 30 days (deduplication check).\n"
        "6. Property located in Florida (or additional states as addended)."
    ),
    "b2b": (
        "1. Company name and primary contact verified.\n"
        "2. Annual revenue ≥ $500,000 or loan volume ≥ $2M/year.\n"
        "3. Decision-maker (C-suite, VP, Owner) reached directly.\n"
        "4. Active business need stated within next 60 days.\n"
        "5. Business located within Buyer's defined territory.\n"
        "6. No prior contact with Buyer in last 90 days (deduplication check)."
    ),
}


# ---------------------------------------------------------------------------
# ContractGenerator
# ---------------------------------------------------------------------------


class ContractGenerator:
    """
    Generates plain-text / Markdown contract documents.

    All methods return a ``str`` suitable for display, download, or storage.
    """

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def generate_msa(self, buyer_info: dict, vertical: str) -> str:
        """
        Generate a full Master Service Agreement for *buyer_info* and
        *vertical*.

        Parameters
        ----------
        buyer_info:
            Dict with keys: company_name, contact_name, address, email, state.
        vertical:
            One of "home_services", "real_estate", "b2b".

        Returns
        -------
        str
            Markdown-formatted MSA document.
        """
        vertical = vertical.lower().replace(" ", "_")
        today = datetime.now(timezone.utc).strftime("%B %d, %Y")
        pricing_block = self._format_pricing_table(vertical)
        qual_criteria = QUALIFICATION_CRITERIA.get(
            vertical, "See vertical-specific addendum."
        )

        return f"""\
# MASTER SERVICE AGREEMENT
## Pay-Per-Qualified-Lead Platform

> **DISCLAIMER:** This document is a template for internal business use only
> and does not constitute legal advice. Consult a licensed attorney before
> execution.

---

**Effective Date:** {today}

---

## 1. Parties

**Service Provider:**
Prime Coastal Funding LLC ("Provider")
Florida, United States
contact@primecoastalfunding.com

**Buyer:**
{buyer_info.get('company_name', '[Company Name]')} ("Buyer")
Attention: {buyer_info.get('contact_name', '[Contact Name]')}
Address: {buyer_info.get('address', '[Address]')}
E-mail: {buyer_info.get('email', '[Email]')}
State of Incorporation / Operation: {buyer_info.get('state', '[State]')}

---

## 2. Services Description

Provider operates a Pay-Per-Qualified-Lead platform for the
**{vertical.replace('_', ' ').title()}** vertical. Provider will identify,
qualify, and deliver sales leads to Buyer pursuant to the qualification
standards defined in Section 3 below. All leads are generated from lawfully
sourced public records and opt-in data.

---

## 3. Lead Qualification Standards

A lead is considered "Qualified" only when ALL of the following criteria are
met prior to delivery:

{qual_criteria}

Provider reserves the right to update qualification criteria with 14 days'
written notice to Buyer.

---

## 4. Pricing and Payment Terms

### 4.1 Per-Lead Pricing

{pricing_block}

Prices are in USD and may be updated with 30 days' written notice.

### 4.2 Payment Method

Buyer must maintain a valid credit card on file with Provider. Charges are
applied **automatically upon each lead delivery** to the card on file.

### 4.3 Monthly Invoice

Provider will generate a monthly invoice summary on the **1st of each
calendar month** covering all leads delivered in the prior month.

### 4.4 Late Payment

Balances unpaid after **15 days** from invoice date accrue interest at
**1.5% per month** (18% per annum) until paid in full.

---

## 5. Lead Delivery Process

Qualified leads are delivered to Buyer via:

- **SMS** to the mobile number on file; and
- **Email** to the address on file.

Delivery occurs within **60 seconds** of final qualification. Buyer
acknowledges that delivery timestamps logged by Provider's platform are
authoritative for dispute-window calculations.

---

## 6. Exclusivity Terms

### 6.1 Geographic Exclusivity (Optional)

Buyer may purchase geographic exclusivity for defined zip codes or counties
(see Addendum). While exclusivity is active, Provider will not sell leads
from the same territory to a direct competitor in the same sub-vertical.

### 6.2 Competitor Restrictions

Buyer may not share or re-sell leads to direct competitors of Provider.
"Direct competitor" means any entity offering a substantially similar
pay-per-lead service targeting the same geographic market.

---

## 7. Dispute Resolution Procedure

### 7.1 Dispute Window

Buyer must submit disputes within **72 hours** of lead delivery. Disputes
submitted after this window are automatically denied.

### 7.2 Submission

Disputes must be submitted via the Provider's Dispute Portal (or by e-mail to
disputes@primecoastalfunding.com) and include:
- Lead ID
- Buyer ID
- Dispute reason (see Section 7.3)
- Supporting evidence (optional)

### 7.3 Dispute Reasons and Handling

| Reason | Handling |
|---|---|
| wrong_number | Auto-approved if call duration < 30 s on record |
| duplicate | Auto-approved if lead delivered twice to same Buyer |
| outside_territory | Auto-approved if zip not in Buyer's territory config |
| not_qualified | Manual review — human verification required |
| fake_lead | Manual review — human verification required |

### 7.4 Resolution Timeline

- Auto-approved decisions: processed **immediately**.
- Manual review: resolved within **5 business days**.

---

## 8. Refund and Credit Policy

### 8.1 Dispute Window

All disputes must be submitted within **72 hours** of lead delivery.

### 8.2 Credits

Approved disputes result in a **credit applied to Buyer's next invoice**.
Provider does not issue cash refunds.

### 8.3 Auto-Approval Criteria

Disputes are auto-approved when objective system data (call duration, delivery
log, territory config) confirms the Buyer's claim (see Section 7.3).

### 8.4 Manual Review Criteria

Disputes requiring subjective evaluation (not_qualified, fake_lead) are
escalated to Provider's Quality Assurance team.

---

## 9. Lead Replacement Guarantee

Provider will issue a replacement lead (equal or greater value) if:

1. A dispute is approved (auto or manual); **and**
2. The approved dispute reason is wrong_number, duplicate, or
   outside_territory; **and**
3. Buyer's account is in good standing (no overdue balances).

Replacement leads are issued within **10 business days** of dispute approval.

---

## 10. Confidentiality

Buyer agrees that all leads, data, and platform information received from
Provider are **Confidential Information**. Buyer shall not:

- Share leads with third parties not employed by Buyer;
- Resell or redistribute leads;
- Use leads for purposes other than direct sales outreach.

This obligation survives termination of the Agreement for **2 years**.

---

## 11. Term and Termination

This Agreement is **month-to-month** and continues until either party
provides **7 days' written notice** of termination. Upon termination:

- All outstanding charges become immediately due.
- Buyer retains rights to previously delivered leads.
- Unused prepaid credits are refunded pro-rata within 30 days.

---

## 12. Limitation of Liability

Provider's total liability to Buyer for any claim arising under this
Agreement shall not exceed **one (1) month's total spend** by Buyer in the
30 days preceding the claim. Provider is not liable for indirect, incidental,
or consequential damages.

---

## 13. Governing Law

This Agreement is governed by the laws of the **State of Florida**, without
regard to conflict-of-law principles. Any disputes not resolved through the
dispute procedure in Section 7 shall be submitted to binding arbitration in
Sarasota County, Florida.

---

## 14. Signatures

By signing below, the parties agree to be bound by this Master Service
Agreement.

**Provider:**

Signature: ______________________________
Name: ______________________________
Title: Authorized Representative, Prime Coastal Funding LLC
Date: ______________________________

**Buyer:**

Signature: ______________________________
Name: {buyer_info.get('contact_name', '______________________________')}
Title: ______________________________
Company: {buyer_info.get('company_name', '______________________________')}
Date: ______________________________

---
*End of Master Service Agreement*
"""

    def generate_vertical_addendum(
        self, vertical: str, sub_vertical: str, buyer_info: dict
    ) -> str:
        """
        Generate a vertical-specific addendum to the MSA.

        Parameters
        ----------
        vertical:
            One of "home_services", "real_estate", "b2b".
        sub_vertical:
            A sub-type within the vertical (e.g., "roofing", "bridge_loan").
        buyer_info:
            Dict with buyer details (same schema as generate_msa).

        Returns
        -------
        str
            Markdown-formatted addendum document.
        """
        vertical = vertical.lower().replace(" ", "_")
        sub_vertical_key = sub_vertical.lower().replace(" ", "_")
        today = datetime.now(timezone.utc).strftime("%B %d, %Y")

        price = PRICING.get(vertical, {}).get(sub_vertical_key)
        price_str = f"${price:.2f} per qualified lead" if price else "See pricing schedule"

        qual_criteria = QUALIFICATION_CRITERIA.get(
            vertical, "Refer to Master Service Agreement Section 3."
        )

        special_terms = self._special_terms(vertical, sub_vertical_key)

        return f"""\
# VERTICAL-SPECIFIC ADDENDUM
## {vertical.replace('_', ' ').title()} — {sub_vertical.replace('_', ' ').title()}

> This Addendum supplements the Master Service Agreement ("MSA") between
> Provider and Buyer dated {today} and is incorporated by reference.

**Buyer:** {buyer_info.get('company_name', '[Company Name]')}
**Contact:** {buyer_info.get('contact_name', '[Contact Name]')}
**Addendum Date:** {today}

---

## A. Sub-Vertical Qualification Criteria

In addition to the general criteria in MSA Section 3, the following
criteria apply specifically to **{sub_vertical.replace('_', ' ').title()}** leads:

{qual_criteria}

---

## B. Pricing Schedule

| Sub-Vertical | Price per Qualified Lead |
|---|---|
| {sub_vertical.replace('_', ' ').title()} | {price_str} |

All prices in USD. Volume discounts apply per the Volume Discount Schedule
(see Section E below).

---

## C. Geographic Territory

Buyer's exclusive territory under this Addendum is defined as:

- **State:** {buyer_info.get('state', 'Florida')}
- **Counties / Zip Codes:** As specified in writing by Buyer at onboarding
  (attach list or complete Provider's Territory Configuration form).

Leads from outside this territory qualify for an auto-approved dispute
(MSA Section 7.3).

---

## D. Volume Commitment

| Tier | Monthly Lead Volume | Discount |
|---|---|---|
| Standard | 1 – 99 leads | 0% |
| Silver | 100 – 249 leads | 0% |
| Gold | 250 – 499 leads | 11% |
| Platinum | 500 – 999 leads | 22% |
| Diamond | 1,000+ leads | 32% |

Volume is calculated per calendar month. Discounts are applied as credits on
the following month's invoice.

---

## E. Special Terms

{special_terms}

---

## F. Signatures

This Addendum is incorporated into and forms part of the MSA.

**Provider:**

Signature: ______________________________
Date: ______________________________

**Buyer:**

Signature: ______________________________
Name: {buyer_info.get('contact_name', '______________________________')}
Date: ______________________________

---
*End of Addendum*
"""

    def generate_lead_delivery_confirmation(
        self,
        lead_data: dict,
        buyer_info: dict,
        charge_amount: float,
    ) -> str:
        """
        Generate a formatted lead delivery receipt.

        Parameters
        ----------
        lead_data:
            Dict with keys: lead_id, name, phone, property_address, lead_type,
            qualification_criteria_met (list of str), delivered_at (datetime or str),
            zip_code (optional).
        buyer_info:
            Dict with buyer details.
        charge_amount:
            Amount in USD charged for this lead.

        Returns
        -------
        str
            Markdown-formatted receipt.
        """
        delivered_at = lead_data.get("delivered_at", datetime.now(timezone.utc))
        if isinstance(delivered_at, str):
            delivered_at_str = delivered_at
        else:
            delivered_at_str = delivered_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        criteria_met = lead_data.get("qualification_criteria_met", [])
        criteria_block = "\n".join(f"- [x] {c}" for c in criteria_met) or "- (none recorded)"

        dispute_deadline = (
            "72 hours from delivery timestamp above"
        )

        return f"""\
# LEAD DELIVERY CONFIRMATION RECEIPT

---

**Receipt ID:** RCPT-{lead_data.get('lead_id', 'UNKNOWN')}
**Delivered To:** {buyer_info.get('company_name', '[Buyer]')} ({buyer_info.get('email', '')})
**Delivery Timestamp:** {delivered_at_str}

---

## Lead Details

| Field | Value |
|---|---|
| Lead ID | {lead_data.get('lead_id', '—')} |
| Contact Name | {lead_data.get('name', '—')} |
| Phone | {lead_data.get('phone', '—')} |
| Property Address | {lead_data.get('property_address', '—')} |
| Lead Type | {lead_data.get('lead_type', '—')} |
| Zip Code | {lead_data.get('zip_code', '—')} |

---

## Qualification Criteria Met

{criteria_block}

---

## Billing

| Description | Amount |
|---|---|
| Lead charge | ${charge_amount:.2f} |
| **Total charged** | **${charge_amount:.2f}** |

Charge applied to payment method on file for
{buyer_info.get('company_name', 'Buyer')}.

---

## Dispute Information

- **Dispute Deadline:** {dispute_deadline}
- **How to Dispute:** Submit via the Contracts & Disputes tab in the
  platform, or e-mail disputes@primecoastalfunding.com with your Lead ID.
- **Required Fields:** Lead ID, Buyer ID, dispute reason, optional evidence.

Disputes submitted after the 72-hour window will be automatically denied
per MSA Section 7.1.

---

*This is an automated receipt generated by Prime Coastal Funding LLC.*
*It does not constitute legal advice.*
"""

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _format_pricing_table(vertical: str) -> str:
        """Return a Markdown pricing table for the given vertical."""
        rows = PRICING.get(vertical, {})
        if not rows:
            return "_Pricing not defined for this vertical. See Addendum._"
        header = "| Sub-Vertical | Price per Lead |\n|---|---|\n"
        lines = [
            f"| {sv.replace('_', ' ').title()} | ${price:.2f} |"
            for sv, price in rows.items()
        ]
        return header + "\n".join(lines)

    @staticmethod
    def _special_terms(vertical: str, sub_vertical: str) -> str:
        """Return vertical/sub-vertical specific special terms."""
        if vertical == "home_services" and "roofing" in sub_vertical:
            return (
                "**Roofing — Insurance Claim Leads:**\n"
                "Leads where the homeowner has an open insurance claim or "
                "scheduled adjuster visit are priced at $120.00 per lead "
                "(see pricing table). Standard roofing leads are $85.00.\n\n"
                "Buyer agrees not to use insurance claim lead data for any "
                "purpose that would violate Florida's anti-steering or "
                "assignment-of-benefits regulations."
            )
        if vertical == "real_estate" and sub_vertical in (
            "bridge_loan", "hard_money"
        ):
            return (
                "**Short-Term Lending Leads:**\n"
                "Leads for bridge loans and hard money are considered "
                "time-sensitive. Buyer agrees to make first contact within "
                "**4 business hours** of delivery. Failure to contact within "
                "this window does not qualify as grounds for a dispute."
            )
        if vertical == "b2b":
            return (
                "**B2B Firmographic Minimum:**\n"
                "Leads will only be delivered when the prospect business "
                "meets the firmographic minimums defined in MSA Section 3. "
                "Buyer acknowledges that B2B leads are verified against "
                "publicly available data and may not reflect real-time "
                "business conditions."
            )
        return "No special terms apply to this sub-vertical beyond those in the MSA."
