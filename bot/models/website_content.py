"""Read-only DTOs for website-owned content consumed by the bot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionMetadata:
    title: str
    tagline: str
    description: str
    genre: str
    runtime: str
    release_date: str
    release_status_label: str
    release_status_headline: str
    release_status_summary: str
    poster_image: str


@dataclass(frozen=True)
class ScreeningOffer:
    name: str
    url: str
    price: float
    price_currency: str
    availability: str
    valid_from: str


@dataclass(frozen=True)
class ScreeningEvent:
    name: str
    description: str
    start_date: str
    end_date: str
    event_status: str
    event_attendance_mode: str
    location_name: str
    location_url: str
    location_street_address: str
    location_locality: str
    location_region: str
    location_postal_code: str
    location_country: str
    video_format: str
    subtitle_language: str
    offers: tuple[ScreeningOffer, ...]


@dataclass(frozen=True)
class CampaignLink:
    label: str
    url: str
    status: str
    description: str
