"""Discord member-join event handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..runtime.client import BotRuntime


def handle_member_join(runtime: "BotRuntime", guild_id: int, discord_user_id: str, display_name: str) -> dict:
    """
    Called when a new member joins a Discord guild.

    Returns a dict with the events created and whether it was a duplicate.
    The actual Discord API calls (role assignment, welcome DM) happen in the
    adapter layer using the returned events as the authoritative source of truth.
    """
    events, was_duplicate = runtime.onboarding_service.handle_member_join(
        guild_id=guild_id,
        discord_user_id=discord_user_id,
        display_name=display_name,
    )

    return {
        'duplicate': was_duplicate,
        'events': events,
        'role_assignments': [
            e for e in events if e.event_type == 'role_assigned'
        ],
        'welcome_sent': any(e.event_type == 'welcome_sent' for e in events),
    }
