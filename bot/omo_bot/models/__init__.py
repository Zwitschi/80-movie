"""Typed bot domain models."""

from .syndication_feed import SyndicationFetchResult, SyndicationItem
from .syndication import SyndicationSourceState
from .website_content import CampaignLink, ProductionMetadata, ScreeningEvent, ScreeningOffer

__all__ = [
    "CampaignLink",
    "ProductionMetadata",
    "ScreeningEvent",
    "ScreeningOffer",
    "SyndicationFetchResult",
    "SyndicationItem",
    "SyndicationSourceState",
]
