"""Queue command handlers for bot-facing join/leave/advance actions."""

from __future__ import annotations

from ..models import QueueEvent, QueueSnapshot
from ..services.queue_service import QueueService, QueueValidationError


def handle_queue_join(
    service: QueueService,
    *,
    queue_id: str,
    guild_id: int,
    label: str,
    discord_user_id: str,
    display_name: str,
    actor_user_id: str | None = None,
    note: str = '',
) -> tuple[QueueSnapshot, QueueEvent]:
    resolved_queue_id = _required_text(queue_id, 'queue_id')
    resolved_label = _required_text(label, 'label')
    resolved_user_id = _required_text(discord_user_id, 'discord_user_id')
    return service.join_queue(
        queue_id=resolved_queue_id,
        guild_id=guild_id,
        label=resolved_label,
        discord_user_id=resolved_user_id,
        display_name=display_name.strip() or resolved_user_id,
        actor_user_id=actor_user_id,
        note=note,
    )


def handle_queue_leave(
    service: QueueService,
    *,
    queue_id: str,
    discord_user_id: str,
    actor_user_id: str | None = None,
    reason: str = '',
) -> tuple[QueueSnapshot, QueueEvent]:
    return service.leave_queue(
        queue_id=_required_text(queue_id, 'queue_id'),
        discord_user_id=_required_text(discord_user_id, 'discord_user_id'),
        actor_user_id=actor_user_id,
        reason=reason,
    )


def handle_queue_advance(
    service: QueueService,
    *,
    queue_id: str,
    actor_user_id: str | None = None,
) -> tuple[QueueSnapshot, QueueEvent]:
    return service.advance_queue(
        queue_id=_required_text(queue_id, 'queue_id'),
        actor_user_id=actor_user_id,
    )


def handle_queue_pause(
    service: QueueService,
    *,
    queue_id: str,
    actor_user_id: str | None = None,
    reason: str = '',
) -> tuple[QueueSnapshot, QueueEvent]:
    return service.pause_queue(
        queue_id=_required_text(queue_id, 'queue_id'),
        actor_user_id=actor_user_id,
        reason=reason,
    )


def handle_queue_resume(
    service: QueueService,
    *,
    queue_id: str,
    actor_user_id: str | None = None,
) -> tuple[QueueSnapshot, QueueEvent]:
    return service.resume_queue(
        queue_id=_required_text(queue_id, 'queue_id'),
        actor_user_id=actor_user_id,
    )


def handle_queue_clear(
    service: QueueService,
    *,
    queue_id: str,
    actor_user_id: str | None = None,
    reason: str = '',
) -> tuple[QueueSnapshot, QueueEvent]:
    return service.clear_queue(
        queue_id=_required_text(queue_id, 'queue_id'),
        actor_user_id=actor_user_id,
        reason=reason,
    )


def _required_text(raw_value: object, field_name: str) -> str:
    value = str(raw_value or '').strip()
    if not value:
        raise QueueValidationError(f'{field_name} is required.')
    return value
