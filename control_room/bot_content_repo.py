"""Content adapter for bot read models owned by control_room."""

from __future__ import annotations

from typing import Callable, Protocol

from bot.models.website_content import (
    CampaignLink,
    ProductionMetadata,
    ScreeningEvent,
    ScreeningOffer,
)

from shared.content_store import get_content_reader


class ContentReaderLike(Protocol):
    def read(self, filename: str) -> dict[str, object]:
        ...


class ContentStoreWebsiteContentRepository:
    def __init__(
        self,
        reader_factory: Callable[[], ContentReaderLike] | None = None,
    ) -> None:
        self._reader_factory = reader_factory or get_content_reader

    def get_production_metadata(self) -> ProductionMetadata:
        reader = self._reader_factory()
        movie_payload = _as_dict(reader.read('movies')).get('movie', {})
        media_payload = _as_dict(reader.read(
            'media_assets')).get('media', {})
        release_status = _as_dict(
            _as_dict(movie_payload).get('release_status'))
        return ProductionMetadata(
            title=_as_str(_as_dict(movie_payload).get('title')),
            tagline=_as_str(_as_dict(movie_payload).get('tagline')),
            description=_as_str(_as_dict(movie_payload).get('description')),
            genre=_as_str(_as_dict(movie_payload).get('genre')),
            runtime=_as_str(_as_dict(movie_payload).get(
                'duration_iso') or _as_dict(movie_payload).get('runtime')),
            release_date=_as_str(_as_dict(movie_payload).get('release_date')),
            release_status_label=_as_str(release_status.get('label')),
            release_status_headline=_as_str(release_status.get('headline')),
            release_status_summary=_as_str(release_status.get('summary')),
            poster_image=_as_str(_as_dict(media_payload).get('poster_image')),
        )

    def list_screening_events(self) -> tuple[ScreeningEvent, ...]:
        reader = self._reader_factory()
        events_payload = _as_dict(reader.read('events')).get('events', [])
        events: list[ScreeningEvent] = []
        for event in _as_list(events_payload):
            event_dict = _as_dict(event)
            location = _as_dict(event_dict.get('location'))
            address = _as_dict(location.get('address'))
            offers = tuple(
                ScreeningOffer(
                    name=_as_str(offer_dict.get('name')),
                    url=_as_str(offer_dict.get('url')),
                    price=_as_float(offer_dict.get('price')),
                    price_currency=_as_str(offer_dict.get('price_currency')),
                    availability=_as_str(offer_dict.get('availability')),
                    valid_from=_as_str(offer_dict.get('valid_from')),
                )
                for offer_dict in (_as_dict(offer) for offer in _as_list(event_dict.get('offers')))
            )
            events.append(
                ScreeningEvent(
                    name=_as_str(event_dict.get('name')),
                    description=_as_str(event_dict.get('description')),
                    start_date=_as_str(event_dict.get('start_date')),
                    end_date=_as_str(event_dict.get('end_date')),
                    event_status=_as_str(event_dict.get('event_status')),
                    event_attendance_mode=_as_str(
                        event_dict.get('event_attendance_mode')),
                    location_name=_as_str(location.get('name')),
                    location_url=_as_str(location.get('url')),
                    location_street_address=_as_str(
                        address.get('street_address')),
                    location_locality=_as_str(address.get('address_locality')),
                    location_region=_as_str(address.get('address_region')),
                    location_postal_code=_as_str(address.get('postal_code')),
                    location_country=_as_str(address.get('address_country')),
                    video_format=_as_str(event_dict.get('video_format')),
                    subtitle_language=_as_str(
                        event_dict.get('subtitle_language')),
                    offers=offers,
                )
            )
        return tuple(events)

    def list_campaign_links(self) -> tuple[CampaignLink, ...]:
        reader = self._reader_factory()
        connect_payload = _as_dict(reader.read(
            'connect')).get('connect', {})
        link_payload = _as_dict(_as_dict(connect_payload).get('links'))
        campaigns = []
        for campaign in _as_list(link_payload.get('campaigns')):
            campaign_dict = _as_dict(campaign)
            campaigns.append(
                CampaignLink(
                    label=_as_str(campaign_dict.get('label')),
                    url=_as_str(campaign_dict.get('url')),
                    status=_as_str(campaign_dict.get('status')),
                    description=_as_str(campaign_dict.get('description')),
                )
            )
        return tuple(campaigns)


def build_content_store_website_content_repository() -> ContentStoreWebsiteContentRepository:
    return ContentStoreWebsiteContentRepository()


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ''


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0
