"""
Tests for utils/data_processor.py and utils/csv_exporter.py
"""

from __future__ import annotations

import io
import pytest
import pandas as pd

from scrapers.base_scraper import LeadType, PropertyRecord
from utils.data_processor import DataProcessor
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
            lead_type=LeadType.FLIPPER.value,
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
