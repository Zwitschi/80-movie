"""Read-only repository contracts for website-owned content."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from ..models.website_content import CampaignLink, ProductionMetadata, ScreeningEvent


class WebsiteContentRepository(Protocol):
    def get_production_metadata(self) -> ProductionMetadata:
        ...

    def list_screening_events(self) -> tuple[ScreeningEvent, ...]:
        ...

    def list_campaign_links(self) -> tuple[CampaignLink, ...]:
        ...


class InMemoryWebsiteContentRepository:
    def __init__(
        self,
        *,
        production_metadata: ProductionMetadata,
        screening_events: tuple[ScreeningEvent, ...] = (),
        campaign_links: tuple[CampaignLink, ...] = (),
    ) -> None:
        self._production_metadata = replace(production_metadata)
        self._screening_events = tuple(replace(event)
                                       for event in screening_events)
        self._campaign_links = tuple(replace(link) for link in campaign_links)

    def get_production_metadata(self) -> ProductionMetadata:
        return replace(self._production_metadata)

    def list_screening_events(self) -> tuple[ScreeningEvent, ...]:
        return tuple(replace(event) for event in self._screening_events)

    def list_campaign_links(self) -> tuple[CampaignLink, ...]:
        return tuple(replace(link) for link in self._campaign_links)
