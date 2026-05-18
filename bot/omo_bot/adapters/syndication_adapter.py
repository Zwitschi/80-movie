"""Contracts for external syndication source adapters."""

from __future__ import annotations

from typing import Protocol

from ..models import SyndicationFetchResult


class SyndicationAdapter(Protocol):
    """Normalize provider data into bot-owned syndication payloads."""

    source_key: str

    def fetch_since(self, *, checkpoint: str | None = None) -> SyndicationFetchResult:
        """Return normalized items newer than checkpoint plus next checkpoint."""
