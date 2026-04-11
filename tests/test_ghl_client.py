"""
Unit tests for ghl/ghl_client.py and ghl/lead_router.py.

All HTTP calls are mocked via unittest.mock — no real network traffic is made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from ghl.ghl_client import GHLClient
from ghl.lead_router import DeliveryResult, LeadRouter


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int = 200, body: dict | None = None) -> MagicMock:
    """Return a mock requests.Response with the given status and JSON body."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.content = b"content"
    _body = body or {}
    resp.json.return_value = _body
    resp.text = json.dumps(_body)
    if status_code >= 400:
        http_err = requests.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# GHLClient — create_contact success path
# ---------------------------------------------------------------------------


class TestCreateContactSuccess:
    """create_contact returns the parsed response body on a 200."""

    def test_create_contact_returns_contact_id(self):
        expected = {"contact": {"id": "cid_001", "firstName": "Jane"}}

        with patch("requests.Session.request", return_value=_mock_response(200, expected)):
            client = GHLClient(api_key="test_key")
            result = client.create_contact({"firstName": "Jane", "lastName": "Doe"})

        assert result == expected
        assert result["contact"]["id"] == "cid_001"

    def test_create_contact_posts_to_correct_endpoint(self):
        """Verify the request is made to /contacts/."""
        with patch("requests.Session.request") as mock_req:
            mock_req.return_value = _mock_response(200, {"contact": {"id": "x"}})
            client = GHLClient(api_key="test_key")
            client.create_contact({"firstName": "Test"})

        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1].endswith("/contacts/")


# ---------------------------------------------------------------------------
# GHLClient — create_contact retry on 429
# ---------------------------------------------------------------------------


class TestCreateContactRetry:
    """create_contact retries on HTTP 429 and succeeds on the third attempt."""

    def test_retries_on_429_then_succeeds(self):
        rate_limited = _mock_response(429, {"message": "Too Many Requests"})
        success = _mock_response(200, {"contact": {"id": "cid_retry"}})

        with patch(
            "requests.Session.request",
            side_effect=[rate_limited, rate_limited, success],
        ):
            client = GHLClient(api_key="test_key")
            result = client.create_contact({"firstName": "Retry"})

        assert result["contact"]["id"] == "cid_retry"

    def test_raises_after_max_retries(self):
        """After 3 failed 429 responses the HTTPError should propagate."""
        rate_limited = _mock_response(429, {"message": "Too Many Requests"})

        with patch(
            "requests.Session.request",
            side_effect=[rate_limited, rate_limited, rate_limited],
        ):
            client = GHLClient(api_key="test_key")
            with pytest.raises(requests.HTTPError):
                client.create_contact({"firstName": "Fail"})


# ---------------------------------------------------------------------------
# GHLClient — add_tag
# ---------------------------------------------------------------------------


class TestAddTag:
    def test_add_tag_success(self):
        expected = {"tags": ["real_estate", "qualified_lead"]}

        with patch(
            "requests.Session.request",
            return_value=_mock_response(200, expected),
        ):
            client = GHLClient(api_key="test_key")
            result = client.add_tag("cid_001", ["real_estate", "qualified_lead"])

        assert result == expected

    def test_add_tag_posts_to_correct_endpoint(self):
        with patch("requests.Session.request") as mock_req:
            mock_req.return_value = _mock_response(200, {})
            client = GHLClient(api_key="test_key")
            client.add_tag("cid_abc", ["tag1"])

        call_args = mock_req.call_args
        assert "cid_abc/tags/" in call_args[0][1]


# ---------------------------------------------------------------------------
# GHLClient — move_pipeline_stage
# ---------------------------------------------------------------------------


class TestMovePipelineStage:
    def test_move_pipeline_stage_success(self):
        expected = {"pipelineStage": {"id": "stage_re_01"}}

        with patch(
            "requests.Session.request",
            return_value=_mock_response(200, expected),
        ):
            client = GHLClient(api_key="test_key")
            result = client.move_pipeline_stage(
                "cid_001", "re_pipeline_001", "stage_re_01"
            )

        assert result == expected

    def test_move_pipeline_stage_sends_correct_payload(self):
        with patch("requests.Session.request") as mock_req:
            mock_req.return_value = _mock_response(200, {})
            client = GHLClient(api_key="test_key")
            client.move_pipeline_stage("cid_x", "pipe_y", "stage_z")

        payload = mock_req.call_args[1]["json"]
        assert payload["contactId"] == "cid_x"
        assert payload["pipelineId"] == "pipe_y"
        assert payload["stageId"] == "stage_z"


# ---------------------------------------------------------------------------
# LeadRouter — home_services lead
# ---------------------------------------------------------------------------


_SAMPLE_HOME_SERVICES_LEAD = {
    "Owner Name": "John Smith",
    "Property Address": "123 Sunrise Blvd, Fort Lauderdale, FL 33301",
    "Mailing Address": "PO Box 999, Fort Lauderdale, FL 33301",
    "County": "Broward",
    "Scraped Emails": "john.smith@example.com",
    "Lead Type": "Fix & Flip Investors",
    "Property Type": "roofing inspection needed",
    "Assessed Value": "310000",
    "Lead Score": "72",
    "Lead Source": "OSINT Scraper",
}


class TestLeadRouterHomeServices:
    def _make_router_with_mocks(self):
        client = GHLClient(api_key="test_key")
        contact_resp = {"contact": {"id": "hs_contact_01"}}
        opp_resp = {"opportunity": {"id": "hs_opp_01"}}
        tag_resp = {"tags": ["home_services"]}

        with patch("requests.Session.request") as mock_req:
            mock_req.side_effect = [
                _mock_response(200, contact_resp),
                _mock_response(200, opp_resp),
                _mock_response(200, tag_resp),
            ]
            router = LeadRouter(client=client)
            result = router.route(_SAMPLE_HOME_SERVICES_LEAD, vertical="home_services")

        return result

    def test_home_services_success(self):
        result = self._make_router_with_mocks()
        assert result.success is True

    def test_home_services_contact_id(self):
        result = self._make_router_with_mocks()
        assert result.contact_id == "hs_contact_01"

    def test_home_services_opportunity_id(self):
        result = self._make_router_with_mocks()
        assert result.opportunity_id == "hs_opp_01"

    def test_home_services_qualified_lead_tag(self):
        result = self._make_router_with_mocks()
        assert "qualified_lead" in result.tags_applied

    def test_home_services_vertical_tag(self):
        result = self._make_router_with_mocks()
        assert "home_services" in result.tags_applied

    def test_home_services_county_tag(self):
        result = self._make_router_with_mocks()
        assert "county:broward" in result.tags_applied

    def test_home_services_no_error(self):
        result = self._make_router_with_mocks()
        assert result.error is None


# ---------------------------------------------------------------------------
# LeadRouter — real_estate lead
# ---------------------------------------------------------------------------


_SAMPLE_REAL_ESTATE_LEAD = {
    "Owner Name": "Maria Lopez",
    "Property Address": "456 Ocean Drive, Miami Beach, FL 33139",
    "County": "Miami-Dade",
    "Scraped Emails": "maria.lopez@example.com",
    "Lead Type": "High Interest / High Equity (DSCR Prospects)",
    "Property Type": "Commercial",
    "Assessed Value": "875000",
    "Equity": "350000",
    "Mortgage Balance": "525000",
    "Lead Score": "80",
    "Lead Source": "OSINT Scraper",
}


class TestLeadRouterRealEstate:
    def _make_router_with_mocks(self):
        client = GHLClient(api_key="test_key")
        contact_resp = {"contact": {"id": "re_contact_01"}}
        opp_resp = {"opportunity": {"id": "re_opp_01"}}
        tag_resp = {"tags": ["real_estate"]}

        with patch("requests.Session.request") as mock_req:
            mock_req.side_effect = [
                _mock_response(200, contact_resp),
                _mock_response(200, opp_resp),
                _mock_response(200, tag_resp),
            ]
            router = LeadRouter(client=client)
            result = router.route(_SAMPLE_REAL_ESTATE_LEAD, vertical="real_estate")

        return result

    def test_real_estate_success(self):
        result = self._make_router_with_mocks()
        assert result.success is True

    def test_real_estate_contact_id(self):
        result = self._make_router_with_mocks()
        assert result.contact_id == "re_contact_01"

    def test_real_estate_opportunity_id(self):
        result = self._make_router_with_mocks()
        assert result.opportunity_id == "re_opp_01"

    def test_real_estate_qualified_lead_tag(self):
        result = self._make_router_with_mocks()
        assert "qualified_lead" in result.tags_applied

    def test_real_estate_vertical_tag(self):
        result = self._make_router_with_mocks()
        assert "real_estate" in result.tags_applied

    def test_real_estate_pipeline_set(self):
        result = self._make_router_with_mocks()
        assert result.pipeline == "re_pipeline_001"

    def test_real_estate_stage_is_new_lead(self):
        result = self._make_router_with_mocks()
        assert result.stage == "stage_re_01"


# ---------------------------------------------------------------------------
# LeadRouter — unknown vertical
# ---------------------------------------------------------------------------


class TestLeadRouterUnknownVertical:
    def test_unknown_vertical_returns_failure(self):
        client = GHLClient(api_key="test_key")
        router = LeadRouter(client=client)
        result = router.route({"Owner Name": "Test"}, vertical="unknown_vertical")
        assert result.success is False
        assert result.error is not None
        assert "unknown_vertical" in result.error.lower()
