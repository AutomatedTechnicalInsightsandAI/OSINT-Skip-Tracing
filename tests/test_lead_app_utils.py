from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from scrapers.base_scraper import LeadType
from utils import lead_app_utils
from utils.lead_app_utils import LEAD_TYPE_HELP, OUTREACH_PRIORITY_COLUMNS


def test_lead_type_help_contains_all_supported_types():
    assert LeadType.CASHOUT_REFI in LEAD_TYPE_HELP
    assert LeadType.BALLOON_PROSPECTS in LEAD_TYPE_HELP
    assert LeadType.TRUST_REFI in LEAD_TYPE_HELP


def test_trust_refi_help_text_mentions_trust_signals():
    help_text = LEAD_TYPE_HELP[LeadType.TRUST_REFI]
    assert "trust" in help_text.lower()
    assert "trustee" in help_text.lower()


def test_balloon_help_text_mentions_2026_2027_and_scan_target():
    help_text = LEAD_TYPE_HELP[LeadType.BALLOON_PROSPECTS]
    assert "2026 or 2027" in help_text
    assert "1,000 PDFs per run" in help_text


def test_outreach_priority_columns_include_mod_strategy_fields():
    expected = [
        "Sales Strategy",
        "Modified Principal",
        "Is HELOC",
        "Credit Limit",
        "Rate Type",
        "Trust Keywords",
    ]
    for col in expected:
        assert col in OUTREACH_PRIORITY_COLUMNS


class _DummyProgress:
    def progress(self, *_args, **_kwargs):
        return None

    def empty(self):
        return None


class _DummyStatus:
    def __init__(self):
        self.messages: list[str] = []

    def write(self, message: str):
        self.messages.append(message)

    def update(self, **_kwargs):
        return None


class _DummyStreamlit:
    def __init__(self):
        self.session_state: dict = {}
        self.warnings: list[str] = []

    def warning(self, message: str):
        self.warnings.append(message)

    def progress(self, *_args, **_kwargs):
        return _DummyProgress()

    def status(self, *_args, **_kwargs):
        return _DummyStatus()

    @contextmanager
    def spinner(self, *_args, **_kwargs):
        yield


class _FakeScraperA:
    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def fetch_records(self, *_args, **_kwargs):
        return [{"County": "Sarasota", "Owner Name": "Lead One"}]


class _FakeScraperB:
    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def fetch_records(self, *_args, **_kwargs):
        return [{"County": "Broward", "Owner Name": "Lead Two"}]


class _FakeProcessor:
    def __init__(self, **_kwargs):
        pass

    def process(self, records):
        return pd.DataFrame(records)


def test_run_scrapers_persists_balloon_partial_results_and_saves_incrementally(monkeypatch):
    st = _DummyStreamlit()
    save_calls: list[tuple[int, str]] = []

    monkeypatch.setattr(lead_app_utils, "st", st)
    monkeypatch.setattr(lead_app_utils, "DataProcessor", _FakeProcessor)
    monkeypatch.setattr(
        lead_app_utils,
        "COUNTY_SCRAPERS",
        {"Sarasota": _FakeScraperA, "Broward": _FakeScraperB},
    )
    monkeypatch.setattr(
        lead_app_utils,
        "save_results_csv",
        lambda df, _lead_type, label: save_calls.append((len(df), label))
        or Path(f"/tmp/{label}.csv"),
    )

    df = lead_app_utils.run_scrapers(
        {
            "counties": ["Sarasota", "Broward"],
            "lead_type": LeadType.BALLOON_PROSPECTS,
            "max_results": 10,
            "headless": True,
            "skip_tracing": False,
        }
    )

    assert len(df) == 2
    assert len(st.session_state["balloon_partial_df"]) == 2
    assert len(st.session_state["balloon_results_df"]) == 2
    assert st.session_state["balloon_saved_csv_path"].endswith(
        "/tmp/balloon_balance_partial.csv"
    )
    assert save_calls == [
        (1, "balloon_balance_partial"),
        (2, "balloon_balance_partial"),
    ]
