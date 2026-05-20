"""Moderation domain service for privileged administrative actions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .queue_service import QueueService
    from .mileage_service import MileageService
    from .onboarding_service import OnboardingService
    from ..repositories.onboarding_repo import OnboardingRepository


class ModerationService:
    def __init__(
        self,
        queue_service: QueueService,
        mileage_service: MileageService,
        onboarding_service: OnboardingService,
        onboarding_repository: OnboardingRepository,
        logger: logging.Logger | None = None,
    ) -> None:
        self._queue_service = queue_service
        self._mileage_service = mileage_service
        self._onboarding_service = onboarding_service
        self._onboarding_repository = onboarding_repository
        self._logger = logger or logging.getLogger(__name__)

    def reset_user_onboarding(
        self,
        *,
        guild_id: int,
        discord_user_id: str,
        actor_user_id: str | None = None,
        reason: str = "",
    ) -> None:
        """Reset a user's onboarding status to pending."""
        state = self._onboarding_repository.get_user_state(
            guild_id, discord_user_id)
        if not state:
            return

        from ..models.onboarding import OnboardingStatus
        from dataclasses import replace
        updated = replace(
            state, status=OnboardingStatus.PENDING, onboarded_at=None)
        self._onboarding_repository.save_user_state(updated)
        self._logger.info(
            "Moderation: User %s onboarding reset by %s. Reason: %s",
            discord_user_id, actor_user_id or "system", reason
        )

    def cleanup_queue(
        self,
        *,
        queue_id: str,
        actor_user_id: str | None = None,
        reason: str = "Moderator cleanup",
    ) -> None:
        """Clear all entries from a queue."""
        self._queue_service.clear_queue(
            queue_id=queue_id,
            actor_user_id=actor_user_id,
            reason=reason,
        )

    def bulk_adjust_mileage(
        self,
        *,
        guild_id: int,
        points_delta: int,
        reason: str,
        actor_user_id: str | None = None,
    ) -> None:
        """Adjust mileage for all users in a guild (placeholder for future bulk op)."""
        # For now, this is a stub as per 'mileage correction' requirements
        # which usually implies individual fixes, already handled by MileageService.
        pass
