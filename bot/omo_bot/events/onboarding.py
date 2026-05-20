"""Event handlers for onboarding flows."""

from __future__ import annotations

from ..services.onboarding_service import OnboardingService


async def handle_guild_member_add(
    service: OnboardingService,
    *,
    guild_id: int,
    discord_user_id: str,
    username: str,
) -> None:
    """Handle a new member joining the guild."""
    service.handle_member_join(
        guild_id=guild_id,
        discord_user_id=discord_user_id,
        metadata={"username": username},
    )


async def handle_onboarding_completed(
    service: OnboardingService,
    *,
    guild_id: int,
    discord_user_id: str,
) -> None:
    """Handle completion of the Discord onboarding flow."""
    service.complete_onboarding(
        guild_id=guild_id,
        discord_user_id=discord_user_id,
    )
