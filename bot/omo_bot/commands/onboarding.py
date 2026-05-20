"""Onboarding command handlers — privileged replay and reset operations."""

from __future__ import annotations

from ..models import OnboardingEvent
from ..services.onboarding_service import OnboardingService


def handle_onboarding_replay(
    service: OnboardingService,
    *,
    guild_id: int,
    discord_user_id: str,
    display_name: str,
    actor_user_id: str,
) -> tuple[list[OnboardingEvent], bool]:
    """
    Replay missed onboarding steps for a member.

    Returns (events_created, was_skipped). Idempotent — skips steps already
    recorded. If all steps are complete, returns ([], True).
    """
    discord_user_id = _required_text(discord_user_id, 'discord_user_id')
    actor_user_id = _required_text(actor_user_id, 'actor_user_id')
    return service.replay_member_onboarding(
        guild_id=guild_id,
        discord_user_id=discord_user_id,
        display_name=display_name.strip() or discord_user_id,
        actor_user_id=actor_user_id,
    )


def handle_onboarding_reset(
    service: OnboardingService,
    *,
    guild_id: int,
    discord_user_id: str,
    display_name: str,
    actor_user_id: str,
    dry_run: bool = False,
) -> tuple[list[OnboardingEvent], int]:
    """
    Fully reset onboarding for a member and replay from scratch.

    Deletes all existing onboarding events for the member, then re-runs the
    full join flow. Returns (new_events, deleted_count).

    If dry_run=True, returns ([], count_that_would_be_deleted) without
    modifying state.

    Destructive — use only for corrections or data fixes.
    """
    discord_user_id = _required_text(discord_user_id, 'discord_user_id')
    actor_user_id = _required_text(actor_user_id, 'actor_user_id')
    return service.reset_member_onboarding(
        guild_id=guild_id,
        discord_user_id=discord_user_id,
        display_name=display_name.strip() or discord_user_id,
        actor_user_id=actor_user_id,
        dry_run=dry_run,
    )


def handle_onboarding_role_cleanup(
    service: OnboardingService,
    *,
    guild_id: int,
    discord_user_id: str,
    display_name: str,
    actor_user_id: str,
) -> OnboardingEvent:
    """
    Record a role cleanup request for a member.

    The bot worker acts on role_cleanup_requested events to remove Discord
    roles. This command only records the request.
    """
    discord_user_id = _required_text(discord_user_id, 'discord_user_id')
    actor_user_id = _required_text(actor_user_id, 'actor_user_id')
    return service.request_role_cleanup(
        guild_id=guild_id,
        discord_user_id=discord_user_id,
        display_name=display_name.strip() or discord_user_id,
        actor_user_id=actor_user_id,
    )


def _required_text(raw_value: object, field_name: str) -> str:
    value = str(raw_value or '').strip()
    if not value:
        raise ValueError(f'{field_name} is required.')
    return value
