"""Shared protocol and row-mapping utilities for onboarding repositories."""

from __future__ import annotations

from typing import Any, Protocol

from ..models import OnboardingEvent


class OnboardingRepository(Protocol):
    def get_config(self, guild_id: int) -> Any | None: ...
    def save_config(self, config: Any) -> Any: ...
    def append_event(self, event: OnboardingEvent) -> OnboardingEvent: ...
    def has_event(self, idempotency_key: str) -> bool: ...
    def list_events(self, guild_id: int, *,
                    limit: int = 50) -> tuple[OnboardingEvent, ...]: ...

    def get_event(self, event_id: str) -> OnboardingEvent | None: ...

    def delete_user_events(self, guild_id: int,
                           discord_user_id: str) -> int: ...

    def count_user_events(self, guild_id: int,
                          discord_user_id: str) -> int: ...

    def list_events_by_type(self, guild_id: int, event_type: str, *,
                            limit: int = 50) -> tuple[OnboardingEvent, ...]: ...


def row_to_event(row: dict[str, Any]) -> OnboardingEvent:
    payload = row.get('payload') or {}
    if not isinstance(payload, dict):
        payload = {}
    return OnboardingEvent(
        event_id=str(row['id']),
        guild_id=int(row['guild_id']),
        discord_user_id=str(row['discord_user_id']),
        display_name=str(row['display_name']),
        event_type=str(row['event_type']),
        role_id=int(row['role_id']) if row.get(
            'role_id') is not None else None,
        role_binding_key=str(row['role_binding_key']) if row.get(
            'role_binding_key') else None,
        idempotency_key=str(row['idempotency_key']),
        actor_user_id=str(row['actor_user_id']) if row.get(
            'actor_user_id') else None,
        metadata=payload,
        created_at=row['created_at'],
    )
