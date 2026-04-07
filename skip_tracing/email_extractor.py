"""
Email pattern extractor using Python's ``re`` library.

Scans raw HTML / plain text for RFC-5321-style email addresses and returns
a de-duplicated, validated list.
"""

from __future__ import annotations

import re
from typing import List

# ---------------------------------------------------------------------------
# Core regex — deliberately conservative to avoid false positives
# ---------------------------------------------------------------------------

_EMAIL_PATTERN = re.compile(
    r"(?<![/@\w])"          # negative lookbehind: not part of a URL or word
    r"[a-zA-Z0-9._%+\-]+"  # local part
    r"@"
    r"[a-zA-Z0-9.\-]+"     # domain
    r"\."
    r"[a-zA-Z]{2,}"         # TLD (at least 2 chars)
    r"(?![.\w])",            # negative lookahead: not followed by another dot/word char
    re.IGNORECASE,
)

# Common non-personal domains to exclude (image/asset placeholders, etc.)
_EXCLUDE_DOMAINS = frozenset(
    {
        "example.com",
        "sentry.io",
        "sentry-cdn.com",
        "githubusercontent.com",
        "w3.org",
        "schema.org",
        "jquery.com",
        "google-analytics.com",
        "facebook.com",
        "twitter.com",
    }
)


class EmailExtractor:
    """Extract and validate email addresses from raw text or HTML."""

    @staticmethod
    def extract(text: str) -> List[str]:
        """
        Return a sorted, de-duplicated list of email addresses found in *text*.

        Parameters
        ----------
        text:
            Raw HTML or plain text to search.
        """
        if not text:
            return []

        candidates = _EMAIL_PATTERN.findall(text)
        seen: set[str] = set()
        results: List[str] = []

        for email in candidates:
            email_lower = email.lower().strip(".")
            domain = email_lower.split("@", 1)[-1]
            if domain in _EXCLUDE_DOMAINS:
                continue
            if email_lower not in seen:
                seen.add(email_lower)
                results.append(email_lower)

        return sorted(results)

    @staticmethod
    def is_valid(email: str) -> bool:
        """
        Return True if *email* matches the expected pattern.

        This is a lightweight syntactic check — not full RFC-5321 validation.
        """
        return bool(_EMAIL_PATTERN.fullmatch(email.strip()))
