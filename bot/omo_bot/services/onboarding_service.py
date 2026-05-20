"""Onboarding domain service — member-join, role-assignment, replay."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..models import OnboardingConfig, OnboardingEvent, OnboardingRoleBinding
from ..repositories.onboarding_repo import OnboardingRepository

if TYPE_CHECKING:
    pass


class OnboardingService:
    """Orchestrates guild onboarding: welcome messages, role assignment, and audit."""

    def __init__(self, onboarding_repository: OnboardingRepository) -> None:
        self._repo = onboarding_repository

    # ------------------------------------------------------------------
    # Config management
    # ------------------------------------------------------------------

    def get_config(self, guild_id: int) -> OnboardingConfig | None:
        return self._repo.get_config(guild_id)

    def save_config(self, config: OnboardingConfig) -> OnboardingConfig:
        return self._repo.save_config(config)

    # ------------------------------------------------------------------
    # Member-join flow (idempotent, retry-safe)
    # ------------------------------------------------------------------

    def handle_member_join(
        self,
        guild_id: int,
        discord_user_id: str,
        display_name: str,
    ) -> tuple[list[OnboardingEvent], bool]:
        """
        Process a new member joining a guild.

        Returns (events_created, was_duplicate). If the join was already processed
        (duplicate event), returns ([], True) without writing any new events.

        The caller is responsible for sending Discord messages / assigning roles
        using the returned events as the authoritative record.
        """
        idempotency_key = f"member_joined:{guild_id}:{discord_user_id}"
        if self._repo.has_event(idempotency_key):
            return [], True

        config = self._repo.get_config(guild_id)
        events: list[OnboardingEvent] = []
        now = datetime.now(tz=timezone.utc)

        # Record the join event
        join_event = OnboardingEvent(
            event_id=str(uuid.uuid4()),
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            display_name=display_name,
            event_type='member_joined',
            role_id=None,
            role_binding_key=None,
            idempotency_key=idempotency_key,
            actor_user_id=None,
            metadata={
                'starter_channel_ids': list(config.starter_channel_ids) if config else [],
            },
            created_at=now,
        )
        events.append(self._repo.append_event(join_event))

        # Record a role-assignment event for each bound role
        if config:
            for binding in config.role_bindings:
                role_key = f"role_assigned:{guild_id}:{discord_user_id}:{binding.binding_key}"
                if not self._repo.has_event(role_key):
                    role_event = OnboardingEvent(
                        event_id=str(uuid.uuid4()),
                        guild_id=guild_id,
                        discord_user_id=discord_user_id,
                        display_name=display_name,
                        event_type='role_assigned',
                        role_id=binding.role_id,
                        role_binding_key=binding.binding_key,
                        idempotency_key=role_key,
                        actor_user_id=None,
                        metadata={'label': binding.label},
                        created_at=now,
                    )
                    events.append(self._repo.append_event(role_event))

            # Record welcome-sent event
            welcome_key = f"welcome_sent:{guild_id}:{discord_user_id}"
            if not self._repo.has_event(welcome_key):
                welcome_event = OnboardingEvent(
                    event_id=str(uuid.uuid4()),
                    guild_id=guild_id,
                    discord_user_id=discord_user_id,
                    display_name=display_name,
                    event_type='welcome_sent',
                    role_id=None,
                    role_binding_key=None,
                    idempotency_key=welcome_key,
                    actor_user_id=None,
                    metadata={
                        'welcome_copy': config.welcome_copy,
                        'starter_channel_ids': list(config.starter_channel_ids),
                    },
                    created_at=now,
                )
                events.append(self._repo.append_event(welcome_event))

        return events, False

    # ------------------------------------------------------------------
    # Operator replay (retry missed/failed onboarding for a specific user)
    # ------------------------------------------------------------------

    def replay_member_onboarding(
        self,
        guild_id: int,
        discord_user_id: str,
        display_name: str,
        actor_user_id: str,
    ) -> tuple[list[OnboardingEvent], bool]:
        """
        Replay onboarding for a member.

        Returns (events_created, was_skipped). If the member has already been
        fully onboarded (all expected events exist), returns ([], True).
        """
        join_key = f"member_joined:{guild_id}:{discord_user_id}"
        if not self._repo.has_event(join_key):
            # Full replay — treat as first join
            events, _ = self.handle_member_join(
                guild_id, discord_user_id, display_name)
            if not events:
                return events, True
            # Overwrite first event type to 'replay' so observers can distinguish
            return events, False

        config = self._repo.get_config(guild_id)
        if config is None:
            return [], True

        now = datetime.now(tz=timezone.utc)
        events: list[OnboardingEvent] = []

        for binding in config.role_bindings:
            role_key = f"role_assigned:{guild_id}:{discord_user_id}:{binding.binding_key}"
            if not self._repo.has_event(role_key):
                role_event = OnboardingEvent(
                    event_id=str(uuid.uuid4()),
                    guild_id=guild_id,
                    discord_user_id=discord_user_id,
                    display_name=display_name,
                    event_type='role_assigned',
                    role_id=binding.role_id,
                    role_binding_key=binding.binding_key,
                    idempotency_key=role_key,
                    actor_user_id=actor_user_id,
                    metadata={'label': binding.label, 'replay': True},
                    created_at=now,
                )
                events.append(self._repo.append_event(role_event))

        welcome_key = f"welcome_sent:{guild_id}:{discord_user_id}"
        if not self._repo.has_event(welcome_key):
            welcome_event = OnboardingEvent(
                event_id=str(uuid.uuid4()),
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                display_name=display_name,
                event_type='welcome_sent',
                role_id=None,
                role_binding_key=None,
                idempotency_key=welcome_key,
                actor_user_id=actor_user_id,
                metadata={
                    'welcome_copy': config.welcome_copy,
                    'starter_channel_ids': list(config.starter_channel_ids),
                    'replay': True,
                },
                created_at=now,
            )
            events.append(self._repo.append_event(welcome_event))

        if not events:
            return [], True

        # Append an explicit replay marker event (no idempotency guard — operator-triggered)
        replay_event = OnboardingEvent(
            event_id=str(uuid.uuid4()),
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            display_name=display_name,
            event_type='replay',
            role_id=None,
            role_binding_key=None,
            idempotency_key=f"replay:{guild_id}:{discord_user_id}:{now.isoformat()}",
            actor_user_id=actor_user_id,
            metadata={'replayed_events': len(events)},
            created_at=now,
        )
        events.append(self._repo.append_event(replay_event))
        return events, False

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_recent_events(self, guild_id: int, *, limit: int = 50) -> tuple[OnboardingEvent, ...]:
        return self._repo.list_events(guild_id, limit=limit)

    def get_event(self, event_id: str) -> OnboardingEvent | None:
        return self._repo.get_event(event_id)

    # ------------------------------------------------------------------
    # Operator reset (clears all events for a member; replay from scratch)
    # ------------------------------------------------------------------

    def reset_member_onboarding(
        self,
        guild_id: int,
        discord_user_id: str,
        display_name: str,
        actor_user_id: str,
        dry_run: bool = False,
    ) -> tuple[list[OnboardingEvent], int]:
        """
        Delete all onboarding events for a member then replay from scratch.

        Returns (new_events, deleted_count). The deleted_count is the number
        of events removed before the fresh replay was run.

        If dry_run=True, counts events that would be deleted without modifying
        state. Returns ([], count).
        """
        if dry_run:
            count = self._repo.count_user_events(guild_id, discord_user_id)
            return [], count
        deleted_count = self._repo.delete_user_events(
            guild_id, discord_user_id)
        events, _ = self.handle_member_join(
            guild_id, discord_user_id, display_name)

        # Tag each new event with the actor so the reset is auditable
        now = datetime.now(tz=timezone.utc)
        reset_marker = OnboardingEvent(
            event_id=str(uuid.uuid4()),
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            display_name=display_name,
            event_type='reset',
            role_id=None,
            role_binding_key=None,
            idempotency_key=f"reset:{guild_id}:{discord_user_id}:{now.isoformat()}",
            actor_user_id=actor_user_id,
            metadata={'deleted_events': deleted_count,
                      'replayed_events': len(events)},
            created_at=now,
        )
        events.append(self._repo.append_event(reset_marker))
        return events, deleted_count

    # ------------------------------------------------------------------
    # Role cleanup
    # ------------------------------------------------------------------

    def request_role_cleanup(
        self,
        guild_id: int,
        discord_user_id: str,
        display_name: str,
        actor_user_id: str,
    ) -> OnboardingEvent:
        """
        Record a request to remove all onboarding roles for a member.

        Does not perform the Discord role removal directly — the bot worker
        acts on pending role_cleanup_requested events.
        """
        now = datetime.now(tz=timezone.utc)
        event = OnboardingEvent(
            event_id=str(uuid.uuid4()),
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            display_name=display_name,
            event_type='role_cleanup_requested',
            role_id=None,
            role_binding_key=None,
            idempotency_key=f"role_cleanup_requested:{guild_id}:{discord_user_id}:{now.isoformat()}",
            actor_user_id=actor_user_id,
            metadata={},
            created_at=now,
        )
        return self._repo.append_event(event)

    def list_pending_role_cleanups(
        self, guild_id: int, *, limit: int = 50
    ) -> tuple[OnboardingEvent, ...]:
        """Return recent role_cleanup_requested events for the guild."""
        return self._repo.list_events_by_type(
            guild_id, 'role_cleanup_requested', limit=limit
        )
