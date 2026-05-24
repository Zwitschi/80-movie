"""In-memory onboarding repository implementation."""

from __future__ import annotations

from dataclasses import replace

from ..models import OnboardingConfig, OnboardingEvent


class InMemoryOnboardingRepository:
    def __init__(self) -> None:
        self._configs: dict[int, OnboardingConfig] = {}
        self._events: dict[str, OnboardingEvent] = {}
        self._idempotency: set[str] = set()

    def get_config(self, guild_id: int) -> OnboardingConfig | None:
        config = self._configs.get(guild_id)
        return replace(config) if config else None

    def save_config(self, config: OnboardingConfig) -> OnboardingConfig:
        stored = replace(config)
        self._configs[config.guild_id] = stored
        return replace(stored)

    def append_event(self, event: OnboardingEvent) -> OnboardingEvent:
        stored = replace(event)
        self._events[event.event_id] = stored
        self._idempotency.add(event.idempotency_key)
        return replace(stored)

    def has_event(self, idempotency_key: str) -> bool:
        return idempotency_key in self._idempotency

    def list_events(self, guild_id: int, *, limit: int = 50) -> tuple[OnboardingEvent, ...]:
        matching = [
            replace(e) for e in self._events.values() if e.guild_id == guild_id
        ]
        matching.sort(key=lambda e: e.created_at, reverse=True)
        return tuple(matching[:limit])

    def get_event(self, event_id: str) -> OnboardingEvent | None:
        event = self._events.get(event_id)
        return replace(event) if event else None

    def delete_user_events(self, guild_id: int, discord_user_id: str) -> int:
        keys_to_remove = [
            k for k, e in self._events.items()
            if e.guild_id == guild_id and e.discord_user_id == discord_user_id
        ]
        idempotency_to_remove = {
            self._events[k].idempotency_key for k in keys_to_remove
        }
        for k in keys_to_remove:
            del self._events[k]
        self._idempotency -= idempotency_to_remove
        return len(keys_to_remove)

    def count_user_events(self, guild_id: int, discord_user_id: str) -> int:
        return sum(
            1 for e in self._events.values()
            if e.guild_id == guild_id and e.discord_user_id == discord_user_id
        )

    def list_events_by_type(
        self, guild_id: int, event_type: str, *, limit: int = 50
    ) -> tuple[OnboardingEvent, ...]:
        matching = [
            replace(e) for e in self._events.values()
            if e.guild_id == guild_id and e.event_type == event_type
        ]
        matching.sort(key=lambda e: e.created_at, reverse=True)
        return tuple(matching[:limit])
