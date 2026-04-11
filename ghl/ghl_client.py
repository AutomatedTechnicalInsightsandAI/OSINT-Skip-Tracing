"""
GoHighLevel REST API Client
============================

Wraps the GoHighLevel v1 REST API with:
- Bearer-token auth from the ``GHL_API_KEY`` environment variable
- ``requests.Session`` for connection reuse
- ``tenacity`` retry logic (3 retries, exponential back-off) on transient errors
- Full request/response logging at DEBUG level

Usage::

    from ghl.ghl_client import GHLClient

    client = GHLClient()
    contact = client.create_contact({"firstName": "Jane", "lastName": "Doe", ...})
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://rest.gohighlevel.com/v1"


def _is_retryable(exc: BaseException) -> bool:
    """Return True for network errors and HTTP 429 / 5xx responses."""
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else 0
        return status == 429 or status >= 500
    return False


class GHLClient:
    """GoHighLevel REST API v1 client.

    Parameters
    ----------
    api_key:
        GHL Bearer token.  Defaults to the ``GHL_API_KEY`` environment variable.
    base_url:
        Override the API base URL (useful for testing).
    timeout:
        Per-request timeout in seconds (default 30).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = _BASE_URL,
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key or os.getenv("GHL_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Version": "2021-07-28",
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        """Execute an HTTP request and return the parsed JSON response.

        Raises
        ------
        requests.HTTPError
            For any non-2xx response after retries are exhausted.
        """
        url = f"{self._base_url}/{path.lstrip('/')}"
        logger.debug("GHL %s %s | body=%s", method.upper(), url, kwargs.get("json"))

        resp = self._session.request(method, url, timeout=self._timeout, **kwargs)

        logger.debug(
            "GHL %s %s → %s | body=%s",
            method.upper(),
            url,
            resp.status_code,
            resp.text[:500],
        )

        resp.raise_for_status()
        return resp.json() if resp.content else {}

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _request_with_retry(self, method: str, path: str, **kwargs: Any) -> dict:
        """Wrapper around :meth:`_request` that adds tenacity retry logic."""
        return self._request(method, path, **kwargs)

    # ------------------------------------------------------------------
    # Contact endpoints
    # ------------------------------------------------------------------

    def create_contact(self, lead_data: dict) -> dict:
        """Create a new contact in GoHighLevel.

        Parameters
        ----------
        lead_data:
            Mapping of GHL contact fields (firstName, lastName, email, phone …).

        Returns
        -------
        dict
            The GHL API response containing at least ``{"contact": {"id": "…"}}``.
        """
        logger.info("GHL create_contact | name=%s", lead_data.get("firstName"))
        return self._request_with_retry("POST", "/contacts/", json=lead_data)

    def update_contact(self, contact_id: str, data: dict) -> dict:
        """Update an existing contact.

        Parameters
        ----------
        contact_id:
            The GHL contact ID returned from :meth:`create_contact`.
        data:
            Fields to update.

        Returns
        -------
        dict
            Updated contact object.
        """
        logger.info("GHL update_contact | id=%s", contact_id)
        return self._request_with_retry("PUT", f"/contacts/{contact_id}", json=data)

    def add_tag(self, contact_id: str, tags: list[str]) -> dict:
        """Add one or more tags to a contact.

        Parameters
        ----------
        contact_id:
            GHL contact ID.
        tags:
            List of tag strings to apply.

        Returns
        -------
        dict
            GHL API response.
        """
        logger.info("GHL add_tag | id=%s tags=%s", contact_id, tags)
        return self._request_with_retry(
            "POST",
            f"/contacts/{contact_id}/tags/",
            json={"tags": tags},
        )

    # ------------------------------------------------------------------
    # Pipeline / Opportunity endpoints
    # ------------------------------------------------------------------

    def move_pipeline_stage(
        self,
        contact_id: str,
        pipeline_id: str,
        stage_id: str,
    ) -> dict:
        """Move a contact to a specific pipeline stage.

        Parameters
        ----------
        contact_id:
            GHL contact ID.
        pipeline_id:
            Target pipeline ID.
        stage_id:
            Target stage ID within the pipeline.

        Returns
        -------
        dict
            GHL API response.
        """
        logger.info(
            "GHL move_pipeline_stage | contact=%s pipeline=%s stage=%s",
            contact_id,
            pipeline_id,
            stage_id,
        )
        payload = {
            "contactId": contact_id,
            "pipelineId": pipeline_id,
            "stageId": stage_id,
        }
        return self._request_with_retry("POST", "/pipelines/", json=payload)

    def create_opportunity(
        self,
        contact_id: str,
        pipeline_id: str,
        stage_id: str,
        value: float,
        name: str,
    ) -> dict:
        """Create an opportunity (deal) in a pipeline for a contact.

        Parameters
        ----------
        contact_id:
            GHL contact ID.
        pipeline_id:
            Target pipeline ID.
        stage_id:
            Initial stage for the opportunity.
        value:
            Estimated monetary value of the deal.
        name:
            Human-readable name for the opportunity.

        Returns
        -------
        dict
            GHL API response containing the new opportunity object.
        """
        logger.info(
            "GHL create_opportunity | contact=%s name=%s value=%.2f",
            contact_id,
            name,
            value,
        )
        payload = {
            "contactId": contact_id,
            "pipelineId": pipeline_id,
            "stageId": stage_id,
            "monetaryValue": value,
            "name": name,
            "status": "open",
        }
        return self._request_with_retry(
            "POST", "/opportunities/", json=payload
        )

    # ------------------------------------------------------------------
    # Messaging endpoints
    # ------------------------------------------------------------------

    def send_sms(self, contact_id: str, message: str) -> dict:
        """Send an SMS to a contact via GHL.

        Parameters
        ----------
        contact_id:
            GHL contact ID.
        message:
            SMS body text.

        Returns
        -------
        dict
            GHL API response.
        """
        logger.info("GHL send_sms | contact=%s", contact_id)
        payload = {
            "type": "SMS",
            "contactId": contact_id,
            "message": message,
        }
        return self._request_with_retry("POST", "/conversations/messages/", json=payload)

    def send_email(
        self,
        contact_id: str,
        subject: str,
        body: str,
    ) -> dict:
        """Send an email to a contact via GHL.

        Parameters
        ----------
        contact_id:
            GHL contact ID.
        subject:
            Email subject line.
        body:
            HTML or plain-text email body.

        Returns
        -------
        dict
            GHL API response.
        """
        logger.info("GHL send_email | contact=%s subject=%s", contact_id, subject)
        payload = {
            "type": "Email",
            "contactId": contact_id,
            "subject": subject,
            "body": body,
        }
        return self._request_with_retry("POST", "/conversations/messages/", json=payload)
