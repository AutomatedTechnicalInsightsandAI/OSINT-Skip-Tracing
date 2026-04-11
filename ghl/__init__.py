"""
GoHighLevel CRM Integration
============================

Public exports for the ``ghl`` package:

- :class:`~ghl.ghl_client.GHLClient` — REST API client
- :class:`~ghl.lead_router.LeadRouter` — lead routing engine
- :mod:`~ghl.pipeline_config` — pipeline / stage configuration
"""

from ghl.ghl_client import GHLClient
from ghl.lead_router import LeadRouter
from ghl import pipeline_config

__all__ = ["GHLClient", "LeadRouter", "pipeline_config"]
