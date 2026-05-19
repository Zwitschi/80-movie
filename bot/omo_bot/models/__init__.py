"""Typed bot domain models."""

from .queue import QueueEntry, QueueEvent, QueueSnapshot, QueueSummary
from .syndication_feed import SyndicationFetchResult, SyndicationItem
from .syndication import SyndicationSourceState
from .website_content import CampaignLink, ProductionMetadata, ScreeningEvent, ScreeningOffer

__all__ = [
    "CampaignLink",
    "ProductionMetadata",
    "QueueEntry",
    "QueueEvent",
    "QueueSnapshot",
    "QueueSummary",
    "ScreeningEvent",
    "ScreeningOffer",
    "SyndicationFetchResult",
    "SyndicationItem",
    "SyndicationSourceState",
]
