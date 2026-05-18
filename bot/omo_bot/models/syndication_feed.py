"""Normalized payload models for syndication adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SyndicationItem:
    """Provider-agnostic content item ready for downstream bot workflows."""

    source_key: str
    external_id: str
    title: str
    canonical_url: str
    published_at: datetime
    summary: str | None = None
    thumbnail_url: str | None = None


@dataclass(frozen=True)
class SyndicationFetchResult:
    """Normalized fetch result plus next checkpoint for later polling."""

    items: tuple[SyndicationItem, ...]
    next_checkpoint: str | None
