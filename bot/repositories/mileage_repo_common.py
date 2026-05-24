"""Shared protocol and row-mapping utilities for mileage repositories."""

from __future__ import annotations

from typing import Any, Protocol

from ..models import MileageEvent, MileageTier, MileageTotal


class MileageRepository(Protocol):
    def list_tiers(self, guild_id: int) -> tuple[MileageTier, ...]:
        ...

    def upsert_tier(self, tier: MileageTier) -> MileageTier:
        ...

    def list_user_totals(
        self,
        guild_id: int,
        *,
        search: str = '',
        tier_id: str | None = None,
    ) -> tuple[MileageTotal, ...]:
        ...

    def get_user_total(self, guild_id: int, discord_user_id: str) -> MileageTotal | None:
        ...

    def save_user_total(self, total: MileageTotal) -> MileageTotal:
        ...

    def append_event(self, event: MileageEvent) -> MileageEvent:
        ...

    def get_event(self, event_id: str) -> MileageEvent | None:
        ...

    def list_user_events(
        self,
        guild_id: int,
        discord_user_id: str,
        *,
        limit: int = 50,
    ) -> tuple[MileageEvent, ...]:
        ...

    def has_reversal_for(self, event_id: str) -> bool:
        ...


def row_to_tier(row: dict[str, Any]) -> MileageTier:
    return MileageTier(
        tier_id=str(row['id']),
        guild_id=int(row['guild_id']),
        name=str(row['name']),
        points_required=int(row['points_required']),
        role_id=int(row['role_id']) if row.get(
            'role_id') is not None else None,
        sort_order=int(row['sort_order']),
        updated_at=row.get('updated_at'),
    )


def row_to_total(row: dict[str, Any]) -> MileageTotal:
    return MileageTotal(
        guild_id=int(row['guild_id']),
        discord_user_id=str(row['discord_user_id']),
        display_name=str(row['display_name']),
        total_points=int(row['total_points']),
        current_tier_id=str(row['current_tier_id']) if row.get(
            'current_tier_id') else None,
        current_tier_name=str(row['current_tier_name']) if row.get(
            'current_tier_name') else None,
        last_event_id=str(row['last_event_id']) if row.get(
            'last_event_id') else None,
        last_event_at=row.get('last_event_at'),
        updated_at=row.get('updated_at'),
    )


def row_to_event(row: dict[str, Any]) -> MileageEvent:
    metadata = row.get('metadata') or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return MileageEvent(
        event_id=str(row['id']),
        guild_id=int(row['guild_id']),
        discord_user_id=str(row['discord_user_id']),
        display_name=str(row['display_name']),
        event_type=str(row['event_type']),
        points_delta=int(row['points_delta']),
        reason=str(row.get('reason') or ''),
        actor_user_id=str(row['actor_user_id']) if row.get(
            'actor_user_id') else None,
        correlation_id=str(row['correlation_id']) if row.get(
            'correlation_id') else None,
        reversed_event_id=str(row['reversed_event_id']) if row.get(
            'reversed_event_id') else None,
        metadata=metadata,
        created_at=row['created_at'],
    )
