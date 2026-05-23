"""Moderation domain unit tests for bot commands and services.

Covers:
- Queue moderation commands: remove_entry, move_entry, clear
- Onboarding reset/replay: domain logic via OnboardingService
- Dry-run paths for queue_clear and onboarding_reset
- Role cleanup: domain-level request_role_cleanup
"""

from __future__ import annotations

import pytest

from bot.omo_bot.commands.onboarding import (
    handle_onboarding_replay,
    handle_onboarding_reset,
    handle_onboarding_role_cleanup,
)
from bot.omo_bot.commands.queue import (
    handle_queue_clear,
    handle_queue_move_entry,
    handle_queue_remove_entry,
)
from bot.omo_bot.models import OnboardingConfig, OnboardingRoleBinding
from bot.omo_bot.repositories.onboarding_repo import InMemoryOnboardingRepository
from bot.omo_bot.repositories.queue_repo import InMemoryQueueRepository
from bot.omo_bot.services.onboarding_service import OnboardingService
from bot.omo_bot.services.queue_service import QueueService, QueueEntryNotFoundError


def _make_queue_service() -> QueueService:
    return QueueService(repository=InMemoryQueueRepository())


def _make_onboarding_service(*, with_config: bool = True) -> OnboardingService:
    repo = InMemoryOnboardingRepository()
    svc = OnboardingService(onboarding_repository=repo)
    if with_config:
        svc.save_config(
            OnboardingConfig(
                guild_id=100,
                welcome_copy="Welcome!",
                starter_channel_ids=(111,),
                role_bindings=(
                    OnboardingRoleBinding(
                        binding_key="member", role_id=999, label="Member"),
                ),
            )
        )
    return svc


def _setup_queue(service: QueueService, *, num_entries: int = 3) -> list[str]:
    service.ensure_queue(queue_id="q1", guild_id=100, label="Test Queue")
    entry_ids = []
    for i in range(1, num_entries + 1):
        snapshot, _ = service.join_queue(
            queue_id="q1", guild_id=100, label="Test Queue",
            discord_user_id=f"user-{i}", display_name=f"User {i}",
        )
        joined_entry = next(e for e in snapshot.entries if e.discord_user_id == f"user-{i}")
        entry_ids.append(joined_entry.entry_id)
    return entry_ids


def test_queue_remove_entry_happy_path():
    svc = _make_queue_service()
    entry_ids = _setup_queue(svc, num_entries=2)
    snapshot, event = handle_queue_remove_entry(
        svc, queue_id="q1", entry_id=entry_ids[0], actor_user_id="mod1", reason="test removal",
    )
    assert event.event_type == "entry_removed"
    remaining_ids = {e.entry_id for e in snapshot.entries}
    assert entry_ids[0] not in remaining_ids
    assert entry_ids[1] in remaining_ids


def test_queue_remove_entry_unknown_entry_raises():
    svc = _make_queue_service()
    _setup_queue(svc, num_entries=1)
    with pytest.raises(QueueEntryNotFoundError):
        handle_queue_remove_entry(svc, queue_id="q1", entry_id="no-such-entry", actor_user_id="mod1")


def test_queue_remove_entry_requires_entry_id():
    svc = _make_queue_service()
    _setup_queue(svc, num_entries=1)
    with pytest.raises(Exception):
        handle_queue_remove_entry(svc, queue_id="q1", entry_id="", actor_user_id="mod1")


def test_queue_move_entry_reorders_waiting_entries():
    svc = _make_queue_service()
    entry_ids = _setup_queue(svc, num_entries=3)
    svc.advance_queue(queue_id="q1", actor_user_id="op1")
    snapshot, event = handle_queue_move_entry(
        svc, queue_id="q1", entry_id=entry_ids[2], target_position=1,
        actor_user_id="mod1", reason="priority bump",
    )
    assert event.event_type == "entry_moved"
    waiting = [e for e in snapshot.entries if e.state == "waiting"]
    assert waiting[0].entry_id == entry_ids[2]


def test_queue_move_entry_requires_queue_id():
    svc = _make_queue_service()
    entry_ids = _setup_queue(svc, num_entries=2)
    with pytest.raises(Exception):
        handle_queue_move_entry(svc, queue_id="", entry_id=entry_ids[0], target_position=1)


def test_onboarding_reset_clears_and_replays():
    svc = _make_onboarding_service()
    events_first, _ = svc.handle_member_join(guild_id=100, discord_user_id="user-1", display_name="Alice")
    assert len(events_first) == 3
    events_reset, deleted = svc.reset_member_onboarding(
        guild_id=100, discord_user_id="user-1", display_name="Alice", actor_user_id="mod1",
    )
    assert deleted == 3
    event_types = {e.event_type for e in events_reset}
    assert "member_joined" in event_types
    assert "role_assigned" in event_types
    assert "welcome_sent" in event_types
    assert "reset" in event_types


def test_onboarding_reset_removes_idempotency_so_rejoin_works():
    svc = _make_onboarding_service()
    svc.handle_member_join(guild_id=100, discord_user_id="user-1", display_name="Alice")
    events_reset, _ = svc.reset_member_onboarding(
        guild_id=100, discord_user_id="user-1", display_name="Alice", actor_user_id="mod1",
    )
    join_events = [e for e in events_reset if e.event_type == "member_joined"]
    assert len(join_events) == 1


def test_onboarding_reset_on_fresh_member_still_works():
    svc = _make_onboarding_service()
    events_reset, deleted = svc.reset_member_onboarding(
        guild_id=100, discord_user_id="user-new", display_name="Bob", actor_user_id="mod1",
    )
    assert deleted == 0
    event_types = {e.event_type for e in events_reset}
    assert "member_joined" in event_types


def test_handle_onboarding_replay_skips_complete_member():
    svc = _make_onboarding_service()
    svc.handle_member_join(guild_id=100, discord_user_id="user-1", display_name="Alice")
    events, was_skipped = handle_onboarding_replay(
        svc, guild_id=100, discord_user_id="user-1", display_name="Alice", actor_user_id="mod1",
    )
    assert was_skipped
    assert events == []


def test_handle_onboarding_reset_command_requires_actor():
    svc = _make_onboarding_service()
    with pytest.raises(ValueError, match="actor_user_id"):
        handle_onboarding_reset(svc, guild_id=100, discord_user_id="user-1", display_name="Alice", actor_user_id="")


def test_queue_clear_dry_run_does_not_clear():
    svc = _make_queue_service()
    _setup_queue(svc, num_entries=2)
    snapshot, event = handle_queue_clear(svc, queue_id="q1", actor_user_id="mod1", dry_run=True)
    assert event.event_id == "dry-run"
    assert event.payload.get("dry_run") is True
    assert len(snapshot.entries) == 2


def test_queue_clear_real_clears_entries():
    svc = _make_queue_service()
    _setup_queue(svc, num_entries=2)
    snapshot, event = handle_queue_clear(svc, queue_id="q1", actor_user_id="mod1", dry_run=False)
    assert event.event_type == "queue_cleared"
    assert len(snapshot.entries) == 0


def test_onboarding_reset_dry_run_returns_count_without_deleting():
    svc = _make_onboarding_service()
    svc.handle_member_join(guild_id=100, discord_user_id="user-1", display_name="Alice")
    events, count = handle_onboarding_reset(
        svc, guild_id=100, discord_user_id="user-1", display_name="Alice",
        actor_user_id="mod1", dry_run=True,
    )
    assert count == 3
    assert events == []
    assert svc.list_recent_events(100) != ()


def test_request_role_cleanup_records_event():
    svc = _make_onboarding_service()
    svc.handle_member_join(guild_id=100, discord_user_id="user-1", display_name="Alice")
    event = svc.request_role_cleanup(
        guild_id=100, discord_user_id="user-1", display_name="Alice", actor_user_id="mod1",
    )
    assert event.event_type == "role_cleanup_requested"
    assert event.actor_user_id == "mod1"
    assert event.discord_user_id == "user-1"


def test_handle_onboarding_role_cleanup_command():
    svc = _make_onboarding_service()
    event = handle_onboarding_role_cleanup(
        svc, guild_id=100, discord_user_id="user-1", display_name="Alice", actor_user_id="mod1",
    )
    assert event.event_type == "role_cleanup_requested"


def test_handle_onboarding_role_cleanup_requires_actor():
    svc = _make_onboarding_service()
    with pytest.raises(ValueError, match="actor_user_id"):
        handle_onboarding_role_cleanup(
            svc, guild_id=100, discord_user_id="user-1", display_name="Alice", actor_user_id="",
        )


def test_list_pending_role_cleanups_returns_events():
    svc = _make_onboarding_service()
    svc.request_role_cleanup(guild_id=100, discord_user_id="user-1", display_name="Alice", actor_user_id="mod1")
    svc.request_role_cleanup(guild_id=100, discord_user_id="user-2", display_name="Bob", actor_user_id="mod1")
    pending = svc.list_pending_role_cleanups(guild_id=100)
    assert len(pending) == 2
    assert all(e.event_type == "role_cleanup_requested" for e in pending)
