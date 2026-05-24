"""In-memory mileage repository implementation."""

from __future__ import annotations

from dataclasses import replace

from ..models import MileageEvent, MileageTier, MileageTotal


class InMemoryMileageRepository:
    def __init__(self) -> None:
        self._tiers: dict[int, dict[str, MileageTier]] = {}
        self._totals: dict[tuple[int, str], MileageTotal] = {}
        self._events: dict[str, MileageEvent] = {}
        self._events_by_user: dict[tuple[int, str], list[str]] = {}

    def list_tiers(self, guild_id: int) -> tuple[MileageTier, ...]:
        tiers = self._tiers.get(guild_id, {}).values()
        return tuple(
            replace(tier)
            for tier in sorted(tiers, key=lambda item: (item.points_required, item.sort_order, item.name.lower(), item.tier_id))
        )

    def upsert_tier(self, tier: MileageTier) -> MileageTier:
        stored = replace(tier)
        self._tiers.setdefault(tier.guild_id, {})[tier.tier_id] = stored
        return replace(stored)

    def list_user_totals(
        self,
        guild_id: int,
        *,
        search: str = '',
        tier_id: str | None = None,
    ) -> tuple[MileageTotal, ...]:
        normalized_search = search.strip().lower()
        totals = [
            replace(total)
            for (stored_guild_id, _), total in self._totals.items()
            if stored_guild_id == guild_id
        ]
        if normalized_search:
            totals = [
                total
                for total in totals
                if normalized_search in total.display_name.lower()
                or normalized_search in total.discord_user_id.lower()
            ]
        if tier_id:
            totals = [total for total in totals if total.current_tier_id == tier_id]
        totals.sort(
            key=lambda item: (
                -item.total_points,
                item.display_name.lower(),
                item.discord_user_id,
            )
        )
        return tuple(totals)

    def get_user_total(self, guild_id: int, discord_user_id: str) -> MileageTotal | None:
        total = self._totals.get((guild_id, discord_user_id))
        return replace(total) if total is not None else None

    def save_user_total(self, total: MileageTotal) -> MileageTotal:
        stored = replace(total)
        self._totals[(total.guild_id, total.discord_user_id)] = stored
        return replace(stored)

    def append_event(self, event: MileageEvent) -> MileageEvent:
        stored = replace(event)
        self._events[event.event_id] = stored
        self._events_by_user.setdefault(
            (event.guild_id, event.discord_user_id), []).insert(0, event.event_id)
        return replace(stored)

    def get_event(self, event_id: str) -> MileageEvent | None:
        event = self._events.get(event_id)
        return replace(event) if event is not None else None

    def list_user_events(
        self,
        guild_id: int,
        discord_user_id: str,
        *,
        limit: int = 50,
    ) -> tuple[MileageEvent, ...]:
        event_ids = self._events_by_user.get(
            (guild_id, discord_user_id), [])[:limit]
        return tuple(replace(self._events[event_id]) for event_id in event_ids)

    def has_reversal_for(self, event_id: str) -> bool:
        return any(event.reversed_event_id == event_id for event in self._events.values())
