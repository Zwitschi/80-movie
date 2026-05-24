"""Mileage / XP domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MileageTier:
    tier_id: str
    guild_id: int
    name: str
    points_required: int
    role_id: int | None
    sort_order: int
    updated_at: datetime | None = None


@dataclass(frozen=True)
class MileageEvent:
    event_id: str
    guild_id: int
    discord_user_id: str
    display_name: str
    event_type: str
    points_delta: int
    reason: str
    actor_user_id: str | None
    correlation_id: str | None
    reversed_event_id: str | None
    metadata: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class MileageTotal:
    guild_id: int
    discord_user_id: str
    display_name: str
    total_points: int
    current_tier_id: str | None
    current_tier_name: str | None
    last_event_id: str | None
    last_event_at: datetime | None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class MileageTierStat:
    tier: MileageTier
    user_count: int


@dataclass(frozen=True)
class MileageUserDetail:
    total: MileageTotal
    current_tier: MileageTier | None
    events: tuple[MileageEvent, ...]
