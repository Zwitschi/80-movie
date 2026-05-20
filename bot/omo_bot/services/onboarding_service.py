"""Onboarding domain service for user join and role assignment flows."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone

from ..models.onboarding import OnboardingStatus, OnboardingUserState
from ..repositories.onboarding_repo import OnboardingRepository


class OnboardingError(RuntimeError):
    pass


class OnboardingService:
    def __init__(self, repository: OnboardingRepository, logger: logging.Logger | None = None) -> None:
        self._repository = repository
        self._logger = logger or logging.getLogger(__name__)

    def handle_member_join(
        self,
        *,
        guild_id: int,
        discord_user_id: str,
        metadata: dict[str, object] | None = None,
    ) -> OnboardingUserState:
        existing = self._repository.get_user_state(guild_id, discord_user_id)
        if existing:
            self._logger.info(
                "User %s rejoined guild %s, current status: %s",
                discord_user_id, guild_id, existing.status
            )
            return existing

        state = OnboardingUserState(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            status=OnboardingStatus.PENDING,
            joined_at=self._utcnow(),
            metadata=metadata or {},
        )
        return self._repository.save_user_state(state)

    def start_onboarding(
        self,
        *,
        guild_id: int,
        discord_user_id: str,
    ) -> OnboardingUserState:
        state = self._get_required_state(guild_id, discord_user_id)
        if state.status == OnboardingStatus.COMPLETED:
            return state

        updated = replace(state, status=OnboardingStatus.IN_PROGRESS)
        return self._repository.save_user_state(updated)

    def complete_onboarding(
        self,
        *,
        guild_id: int,
        discord_user_id: str,
    ) -> OnboardingUserState:
        state = self._get_required_state(guild_id, discord_user_id)
        if state.status == OnboardingStatus.COMPLETED:
            return state

        now = self._utcnow()
        updated = replace(
            state,
            status=OnboardingStatus.COMPLETED,
            onboarded_at=now,
        )
        return self._repository.save_user_state(updated)

    def record_role_assigned(
        self,
        *,
        guild_id: int,
        discord_user_id: str,
        role_id: int,
    ) -> OnboardingUserState:
        state = self._get_required_state(guild_id, discord_user_id)
        roles = set(state.metadata.get("assigned_roles", []))
        roles.add(role_id)

        metadata = dict(state.metadata)
        metadata["assigned_roles"] = sorted(list(roles))

        updated = replace(state, metadata=metadata)
        return self._repository.save_user_state(updated)

    def _get_required_state(self, guild_id: int, discord_user_id: str) -> OnboardingUserState:
        state = self._repository.get_user_state(guild_id, discord_user_id)
        if not state:
            # Auto-create if missing (e.g. joined while bot was offline)
            return self.handle_member_join(guild_id=guild_id, discord_user_id=discord_user_id)
        return state

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)
