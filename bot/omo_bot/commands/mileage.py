"""Mileage command handlers for bot-facing XP operations."""

from __future__ import annotations

from ..models import MileageEvent, MileageUserDetail
from ..services.mileage_service import MileageService, MileageValidationError


def handle_mileage_adjust(
    service: MileageService,
    *,
    guild_id: int,
    discord_user_id: str,
    display_name: str,
    points_delta: int,
    reason: str,
    actor_user_id: str | None = None,
    correlation_id: str | None = None,
) -> tuple[MileageUserDetail, MileageEvent]:
    resolved_user_id = _required_text(discord_user_id, 'discord_user_id')
    return service.adjust_user_mileage(
        guild_id=guild_id,
        discord_user_id=resolved_user_id,
        display_name=display_name.strip() or resolved_user_id,
        points_delta=points_delta,
        reason=_required_text(reason, 'reason'),
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )


def handle_mileage_reverse(
    service: MileageService,
    *,
    guild_id: int,
    event_id: str,
    reason: str,
    actor_user_id: str | None = None,
) -> tuple[MileageUserDetail, MileageEvent]:
    return service.reverse_event(
        guild_id=guild_id,
        event_id=_required_text(event_id, 'event_id'),
        reason=_required_text(reason, 'reason'),
        actor_user_id=actor_user_id,
    )


def _required_text(raw_value: object, field_name: str) -> str:
    value = str(raw_value or '').strip()
    if not value:
        raise MileageValidationError(f'{field_name} is required.')
    return value
