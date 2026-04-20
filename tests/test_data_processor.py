"""
Tests for utils/data_processor.py and utils/csv_exporter.py
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
import pytest
import pandas as pd

from scrapers.base_scraper import LeadType, PropertyRecord
from utils.data_processor import DataProcessor, classify_lead
from utils.csv_exporter import CSVExporter


# ---------------------------------------------------------------------------
# DataProcessor — without skip tracing
# ---------------------------------------------------------------------------


def _make_records(n: int = 3) -> list[PropertyRecord]:
    return [
        PropertyRecord(
            owner_name=f"Owner {i}",
            property_address=f"{i} Ocean Drive, Sarasota, FL",
            mailing_address=f"PO Box {i}, Sarasota, FL 34201",
            last_sale_date="06/15/2023",
            estimated_interest_rate="~6.81%",
            scraped_emails="",
            county="Sarasota",
            lead_type=LeadType.BALLOON_PROSPECTS.value,
            sale_price="250000",
            just_value="500000",
            assessed_value="350000",
            taxable_value="340000",
            mtg_amt_at_purchase="200000",
            year_built="1975",
            property_type="Condominium",
            vacant_improved="V",
        )
        for i in range(1, n + 1)
    ]


@pytest.fixture()
def processor_no_skip() -> DataProcessor:
    return DataProcessor(enable_skip_tracing=False)


def test_process_returns_dataframe(processor_no_skip):
    records = _make_records(5)
    df = processor_no_skip.process(records)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 5


def test_process_empty_records(processor_no_skip):
    df = processor_no_skip.process([])
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_process_required_columns_present(processor_no_skip):
    records = _make_records(2)
    df = processor_no_skip.process(records)
    required = [
        "Owner Name",
        "Property Address",
        "Mailing Address",
        "Last Sale Date",
        "Estimated Interest Rate",
        "Scraped Emails",
        "Est Equity Pct",
        "Absentee Owner",
        "Lead Score",
    ]
    for col in required:
        assert col in df.columns, f"Missing required column: {col}"


def test_process_required_columns_first(processor_no_skip):
    """Required columns must appear in the first 6 positions."""
    records = _make_records(2)
    df = processor_no_skip.process(records)
    first_cols = list(df.columns[:6])
    assert "Owner Name" in first_cols
    assert "Scraped Emails" in first_cols


def test_process_data_values_preserved(processor_no_skip):
    records = _make_records(1)
    df = processor_no_skip.process(records)
    assert df.iloc[0]["Owner Name"] == "Owner 1"
    assert df.iloc[0]["Last Sale Date"] == "06/15/2023"
    assert df.iloc[0]["Mtg Amt At Purchase"] == "200000"


def test_process_adds_equity_and_flags(processor_no_skip):
    records = _make_records(1)
    df = processor_no_skip.process(records)
    row = df.iloc[0]
    assert pytest.approx(row["Est Equity Pct"], 0.0001) == 0.6
    assert bool(row["Absentee Owner"]) is True
    assert bool(row["DSCR Prospect"]) is True


def test_process_flags_cashout_refi_candidates(processor_no_skip):
    peak_rate_date = "08/15/2024"
    record = PropertyRecord(
        owner_name="Cash Buyer",
        property_address="10 Bay St, Sarasota, FL",
        mailing_address="10 Bay St, Sarasota, FL",
        last_sale_date=peak_rate_date,
        county="Sarasota",
        lead_type=LeadType.CASHOUT_REFI.value,
        sale_price="450000",
        just_value="470000",
        assessed_value="470000",
        taxable_value="470000",
        mtg_amt_at_purchase="0",
    )
    df = processor_no_skip.process([record])
    row = df.iloc[0]
    assert bool(row["Recent Purchase Candidate"]) is False
    assert bool(row["Peak Rate Purchase Candidate"]) is True
    assert bool(row["Cash-Out Refi Candidate"]) is True
    assert row["Lead Strategy"] == LeadType.CASHOUT_REFI.value


def test_process_flags_maturing_loan_candidates(processor_no_skip):
    upcoming = (datetime.now() + timedelta(days=180)).strftime("%B %d, %Y")
    record = PropertyRecord(
        owner_name="Balloon Borrower",
        property_address="99 Finance Way, Sarasota, FL",
        mailing_address="PO Box 99, Tampa, FL",
        last_sale_date="06/15/2023",
        county="Sarasota",
        lead_type=LeadType.BALLOON_PROSPECTS.value,
        sale_price="650000",
        just_value="800000",
        assessed_value="700000",
        taxable_value="700000",
        mtg_amt_at_purchase="250000",
        lender_name="Bank of America, N. A",
        maturity_date=upcoming,
    )
    df = processor_no_skip.process([record])
    row = df.iloc[0]
    assert bool(row["Maturing Loan Candidate"]) is True
    assert row["Lead Strategy"] == LeadType.BALLOON_PROSPECTS.value
    assert float(row["Months To Maturity"]) > 0


def test_process_preserves_balloon_prospects_lead_type(processor_no_skip):
    upcoming = (datetime.now() + timedelta(days=180)).strftime("%B %d, %Y")
    record = PropertyRecord(
        owner_name="SUNCOAST OFFICE PARK LLC",
        property_address="100 Commerce Blvd, Sarasota, FL",
        mailing_address="200 Finance Way, Tampa, FL",
        last_sale_date="06/15/2021",
        county="Sarasota",
        lead_type=LeadType.BALLOON_PROSPECTS.value,
        sale_price="1500000",
        just_value="1800000",
        assessed_value="1600000",
        taxable_value="1600000",
        mtg_amt_at_purchase="950000",
        lender_name="Regional Bank",
        maturity_date=upcoming,
    )
    df = processor_no_skip.process([record])
    row = df.iloc[0]
    assert bool(row["Maturing Loan Candidate"]) is True
    assert row["Lead Strategy"] == LeadType.BALLOON_PROSPECTS.value
    assert int(row["Lead Score"]) >= 35


def test_classify_lead_prefers_heloc():
    strategy = classify_lead(
        {
            "Owner Name": "ANY OWNER",
            "Is HELOC": "true",
            "Balloon Balance": "90000",
            "Maturity Date": "November 10, 2027",
        }
    )
    assert strategy == "HELOC – Review Credit Limit & Terms"


def test_classify_lead_cashout_refi_for_zero_purchase_mortgage():
    strategy = classify_lead(
        {
            "Owner Name": "ANY OWNER",
            "Property Address": "10 MAIN ST",
            "Mailing Address": "10 MAIN ST",
            "Mtg Amt At Purchase": "0",
            "Sale Price": "450000",
            "Just Value": "500000",
            "Modified Principal": "350000",
        }
    )
    assert strategy == "Cash-Out Refi Candidate – Equity Available"


def test_classify_lead_cashout_refi_for_low_ltv():
    strategy = classify_lead(
        {
            "Owner Name": "ANY OWNER",
            "Property Address": "10 MAIN ST",
            "Mailing Address": "10 MAIN ST",
            "Mtg Amt At Purchase": "220000",
            "Sale Price": "400000",
            "Modified Principal": "250000",
        }
    )
    assert strategy == "Cash-Out Refi Candidate – Equity Available"


def test_process_applies_sales_strategy_classification(processor_no_skip):
    record = PropertyRecord(
        owner_name="SUNCOAST LIVING TRUST",
        property_address="10 MAIN ST",
        mailing_address="PO BOX 20",
        sale_price="250000",
        just_value="500000",
        assessed_value="450000",
        taxable_value="440000",
        mtg_amt_at_purchase="200000",
        county="Sarasota",
        lead_type=LeadType.BALLOON_PROSPECTS.value,
        sales_strategy="Mortgage Mod – Review for Refi",
    )
    df = processor_no_skip.process([record])
    assert df.iloc[0]["Sales Strategy"] == "Trust DSCR Candidate – Absentee Owner"


# ---------------------------------------------------------------------------
# CSVExporter
# ---------------------------------------------------------------------------


def _make_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Owner Name": ["Alice", "Bob"],
            "Property Address": ["1 Main St", "2 Oak Ave"],
            "Mailing Address": ["PO Box 1", "PO Box 2"],
            "Last Sale Date": ["01/01/2023", "06/01/2022"],
            "Estimated Interest Rate": ["~6.81%", "~5.34%"],
            "Scraped Emails": ["alice@test.com", ""],
        }
    )


def test_csv_exporter_to_bytes_type():
    df = _make_df()
    result = CSVExporter.to_bytes(df)
    assert isinstance(result, bytes)


def test_csv_exporter_to_bytes_has_headers():
    df = _make_df()
    csv_text = CSVExporter.to_bytes(df).decode("utf-8")
    assert "Owner Name" in csv_text
    assert "Property Address" in csv_text


def test_csv_exporter_to_bytes_has_data():
    df = _make_df()
    csv_text = CSVExporter.to_bytes(df).decode("utf-8")
    assert "Alice" in csv_text
    assert "alice@test.com" in csv_text


def test_csv_exporter_to_bytes_roundtrip():
    df = _make_df()
    csv_bytes = CSVExporter.to_bytes(df)
    df2 = pd.read_csv(io.BytesIO(csv_bytes))
    assert list(df2.columns) == list(df.columns)
    assert len(df2) == len(df)


def test_csv_exporter_to_file(tmp_path):
    df = _make_df()
    out_path = tmp_path / "leads.csv"
    result = CSVExporter.to_file(df, out_path)
    assert result.exists()
    df2 = pd.read_csv(result)
    assert len(df2) == 2
    assert "Owner Name" in df2.columns
