"""Onboarding domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class OnboardingConfig:
    """Guild-level onboarding configuration."""

    guild_id: int
    welcome_copy: str
    starter_channel_ids: tuple[int, ...]
    role_bindings: tuple[OnboardingRoleBinding, ...]
    updated_at: datetime | None = None


@dataclass(frozen=True)
class OnboardingRoleBinding:
    """Maps a named binding to a Discord role ID for onboarding assignment."""

    binding_key: str
    role_id: int
    label: str


@dataclass(frozen=True)
class OnboardingEvent:
    """Record of a member-join or role-assignment onboarding action."""

    event_id: str
    guild_id: int
    discord_user_id: str
    display_name: str
    event_type: str           # 'member_joined' | 'role_assigned' | 'welcome_sent' | 'replay'
    role_id: int | None
    role_binding_key: str | None
    idempotency_key: str      # prevents duplicate processing
    actor_user_id: str | None
    metadata: dict[str, object]
    created_at: datetime
