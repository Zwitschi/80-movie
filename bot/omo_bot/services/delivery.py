"""Delivery seam for normalized syndication items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import SyndicationItem


@dataclass(frozen=True)
class SyndicationDeliveryBatch:
    """Normalized batch ready for downstream publish or queue handling."""

    source_key: str
    items: tuple[SyndicationItem, ...]


class SyndicationDeliverySink(Protocol):
    """Explicit seam between polling and downstream posting or queue work."""

    def deliver(self, batch: SyndicationDeliveryBatch) -> None:
        """Accept normalized items for later posting or queue processing."""


class NullSyndicationDeliverySink:
    """Default delivery sink used while posting contract settles."""

    def deliver(self, batch: SyndicationDeliveryBatch) -> None:
        return None
