"""Moderation domain unit tests and E2E tests for bot API.

Covers:
- Queue moderation commands: remove_entry, move_entry
- Onboarding reset: full-reset + replay via OnboardingService
- Dry-run paths for queue_clear and onboarding_reset
- Role cleanup: request_role_cleanup domain + API
- Diagnostics: GET /bot/api/diagnostics
- Control-room onboarding reset API (E2E with monkeypatched service)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_queue_service() -> QueueService:
    return QueueService(repository=InMemoryQueueRepository())


def _make_onboarding_service(*, with_config: bool = True) -> OnboardingService:
    repo = InMemoryOnboardingRepository()
    svc = OnboardingService(onboarding_repository=repo)
    if with_config:
        svc.save_config(
            OnboardingConfig(
                guild_id=100,
                welcome_copy='Welcome!',
                starter_channel_ids=(111,),
                role_bindings=(
                    OnboardingRoleBinding(
                        binding_key='member', role_id=999, label='Member'),
                ),
            )
        )
    return svc


def _setup_queue(service: QueueService, *, num_entries: int = 3) -> list[str]:
    """Create a queue with `num_entries` users joined. Returns list of entry_ids."""
    service.ensure_queue(
        queue_id='q1',
        guild_id=100,
        label='Test Queue',
    )
    entry_ids = []
    for i in range(1, num_entries + 1):
        snapshot, _ = service.join_queue(
            queue_id='q1',
            guild_id=100,
            label='Test Queue',
            discord_user_id=f'user-{i}',
            display_name=f'User {i}',
        )
        joined_entry = next(
            e for e in snapshot.entries if e.discord_user_id == f'user-{i}'
        )
        entry_ids.append(joined_entry.entry_id)
    return entry_ids


# ---------------------------------------------------------------------------
# Queue moderation — remove_entry
# ---------------------------------------------------------------------------

def test_queue_remove_entry_happy_path():
    svc = _make_queue_service()
    entry_ids = _setup_queue(svc, num_entries=2)

    snapshot, event = handle_queue_remove_entry(
        svc,
        queue_id='q1',
        entry_id=entry_ids[0],
        actor_user_id='mod1',
        reason='test removal',
    )

    assert event.event_type == 'entry_removed'
    remaining_ids = {e.entry_id for e in snapshot.entries}
    assert entry_ids[0] not in remaining_ids
    assert entry_ids[1] in remaining_ids


def test_queue_remove_entry_unknown_entry_raises():
    svc = _make_queue_service()
    _setup_queue(svc, num_entries=1)

    with pytest.raises(QueueEntryNotFoundError):
        handle_queue_remove_entry(
            svc,
            queue_id='q1',
            entry_id='no-such-entry',
            actor_user_id='mod1',
        )


def test_queue_remove_entry_requires_entry_id():
    svc = _make_queue_service()
    _setup_queue(svc, num_entries=1)

    with pytest.raises(Exception):
        handle_queue_remove_entry(
            svc, queue_id='q1', entry_id='', actor_user_id='mod1')


# ---------------------------------------------------------------------------
# Queue moderation — move_entry
# ---------------------------------------------------------------------------

def test_queue_move_entry_reorders_waiting_entries():
    svc = _make_queue_service()
    entry_ids = _setup_queue(svc, num_entries=3)

    # Advance to make user-1 active, leaving user-2 and user-3 waiting
    svc.advance_queue(queue_id='q1', actor_user_id='op1')

    # Move user-3 (position 2) to position 1
    snapshot, event = handle_queue_move_entry(
        svc,
        queue_id='q1',
        entry_id=entry_ids[2],
        target_position=1,
        actor_user_id='mod1',
        reason='priority bump',
    )

    assert event.event_type == 'entry_moved'
    waiting = [e for e in snapshot.entries if e.state == 'waiting']
    assert waiting[0].entry_id == entry_ids[2]


def test_queue_move_entry_requires_queue_id():
    svc = _make_queue_service()
    entry_ids = _setup_queue(svc, num_entries=2)

    with pytest.raises(Exception):
        handle_queue_move_entry(
            svc, queue_id='', entry_id=entry_ids[0], target_position=1
        )


# ---------------------------------------------------------------------------
# Onboarding reset — OnboardingService.reset_member_onboarding
# ---------------------------------------------------------------------------

def test_onboarding_reset_clears_and_replays():
    svc = _make_onboarding_service()

    # First join
    events_first, _ = svc.handle_member_join(
        guild_id=100, discord_user_id='user-1', display_name='Alice'
    )
    assert len(events_first) == 3  # joined + role + welcome

    # Reset
    events_reset, deleted = svc.reset_member_onboarding(
        guild_id=100,
        discord_user_id='user-1',
        display_name='Alice',
        actor_user_id='mod1',
    )

    assert deleted == 3  # original 3 events deleted
    event_types = {e.event_type for e in events_reset}
    assert 'member_joined' in event_types
    assert 'role_assigned' in event_types
    assert 'welcome_sent' in event_types
    assert 'reset' in event_types


def test_onboarding_reset_removes_idempotency_so_rejoin_works():
    svc = _make_onboarding_service()

    svc.handle_member_join(
        guild_id=100, discord_user_id='user-1', display_name='Alice')

    # After reset, handle_member_join should not treat it as duplicate
    events_reset, _ = svc.reset_member_onboarding(
        guild_id=100, discord_user_id='user-1', display_name='Alice', actor_user_id='mod1'
    )

    join_events = [e for e in events_reset if e.event_type == 'member_joined']
    assert len(join_events) == 1


def test_onboarding_reset_on_fresh_member_still_works():
    svc = _make_onboarding_service()

    # Reset a member who has never joined
    events_reset, deleted = svc.reset_member_onboarding(
        guild_id=100, discord_user_id='user-new', display_name='Bob', actor_user_id='mod1'
    )

    assert deleted == 0
    event_types = {e.event_type for e in events_reset}
    assert 'member_joined' in event_types


# ---------------------------------------------------------------------------
# handle_onboarding_replay command wrapper
# ---------------------------------------------------------------------------

def test_handle_onboarding_replay_skips_complete_member():
    svc = _make_onboarding_service()
    svc.handle_member_join(
        guild_id=100, discord_user_id='user-1', display_name='Alice')

    events, was_skipped = handle_onboarding_replay(
        svc,
        guild_id=100,
        discord_user_id='user-1',
        display_name='Alice',
        actor_user_id='mod1',
    )

    assert was_skipped
    assert events == []


def test_handle_onboarding_reset_command_requires_actor():
    svc = _make_onboarding_service()

    with pytest.raises(ValueError, match='actor_user_id'):
        handle_onboarding_reset(
            svc,
            guild_id=100,
            discord_user_id='user-1',
            display_name='Alice',
            actor_user_id='',
        )


# ---------------------------------------------------------------------------
# E2E — control_room reset_onboarding_api
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from bot_api.app import create_app as create_bot_api_app
    app = create_bot_api_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _set_operator_session(client):
    import bot_api.admin_bot as admin_bot
    with client.session_transaction() as sess:
        sess[admin_bot.BOT_OPS_SESSION_KEY] = 'op-user'
        sess[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'onboarding.read', 'onboarding.write']
        sess[admin_bot.BOT_OPS_LOGIN_AT_KEY] = '2026-05-20T10:00:00Z'
        sess[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = '2026-05-20T10:00:00Z'


def test_reset_onboarding_api_calls_service(client, monkeypatch):
    """POST /onboarding/reset delegates to service and returns JSON."""
    import bot_api.admin_bot as admin_bot

    called_reset: list[dict] = []

    class _PatchedService:
        def reset_member_onboarding(self, guild_id, discord_user_id, display_name, actor_user_id, dry_run=False):
            called_reset.append({
                'guild_id': guild_id,
                'discord_user_id': discord_user_id,
                'actor_user_id': actor_user_id,
            })
            from bot.omo_bot.models import OnboardingEvent
            from datetime import datetime, timezone
            marker = OnboardingEvent(
                event_id='ev-1',
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                display_name=display_name,
                event_type='reset',
                role_id=None,
                role_binding_key=None,
                idempotency_key='reset:100:user-1:now',
                actor_user_id=actor_user_id,
                metadata={'deleted_events': 3, 'replayed_events': 1},
                created_at=datetime.now(timezone.utc),
            )
            return [marker], 3

    monkeypatch.setattr(admin_bot, '_build_onboarding_service',
                        lambda: _PatchedService())
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)

    _set_operator_session(client)

    response = client.post(
        '/bot/onboarding/reset',
        json={'guild_id': 100, 'discord_user_id': 'user-1',
              'display_name': 'Alice', 'confirm': 'reset'},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['deleted_events'] == 3
    assert data['data']['replayed_events'] == 1
    assert called_reset[0]['guild_id'] == 100
    assert called_reset[0]['discord_user_id'] == 'user-1'


def test_reset_onboarding_api_requires_guild_and_user(client, monkeypatch):
    import bot_api.admin_bot as admin_bot
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    _set_operator_session(client)

    response = client.post('/bot/onboarding/reset', json={})
    assert response.status_code == 400


def test_reset_onboarding_api_requires_operator_scope(client):
    """No session → scope denied."""
    response = client.post(
        '/bot/onboarding/reset',
        json={'guild_id': 100, 'discord_user_id': 'user-1'},
    )
    assert response.status_code in (401, 403)


def test_reset_onboarding_api_requires_confirm(client, monkeypatch):
    """POST without confirm='reset' returns 400."""
    import bot_api.admin_bot as admin_bot
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    _set_operator_session(client)

    response = client.post(
        '/bot/onboarding/reset',
        json={'guild_id': 100, 'discord_user_id': 'user-1'},
    )
    assert response.status_code == 400
    assert 'confirm' in response.get_json()['error'].lower()


# ---------------------------------------------------------------------------
# Dry-run — queue clear
# ---------------------------------------------------------------------------

def test_queue_clear_dry_run_does_not_clear():
    """dry_run=True returns preview event without removing entries."""
    svc = _make_queue_service()
    _setup_queue(svc, num_entries=2)

    snapshot, event = handle_queue_clear(
        svc, queue_id='q1', actor_user_id='mod1', dry_run=True)

    assert event.event_id == 'dry-run'
    assert event.payload.get('dry_run') is True
    # Entries should still be in the snapshot (not cleared)
    assert len(snapshot.entries) == 2


def test_queue_clear_real_clears_entries():
    """dry_run=False (default) actually clears the queue."""
    svc = _make_queue_service()
    _setup_queue(svc, num_entries=2)

    snapshot, event = handle_queue_clear(
        svc, queue_id='q1', actor_user_id='mod1', dry_run=False)

    assert event.event_type == 'queue_cleared'
    assert len(snapshot.entries) == 0


# ---------------------------------------------------------------------------
# Dry-run — onboarding reset
# ---------------------------------------------------------------------------

def test_onboarding_reset_dry_run_returns_count_without_deleting():
    """dry_run=True returns deleted count without modifying state."""
    svc = _make_onboarding_service()
    svc.handle_member_join(
        guild_id=100, discord_user_id='user-1', display_name='Alice')

    events, count = handle_onboarding_reset(
        svc,
        guild_id=100,
        discord_user_id='user-1',
        display_name='Alice',
        actor_user_id='mod1',
        dry_run=True,
    )

    assert count == 3           # 3 events exist: joined, role_assigned, welcome_sent
    assert events == []         # nothing replayed
    # State unchanged — events still exist
    assert svc.list_recent_events(100) != ()


def test_reset_onboarding_api_dry_run_does_not_require_confirm(client, monkeypatch):
    """dry_run=True skips confirm requirement and does not delete."""
    import bot_api.admin_bot as admin_bot

    called: list[dict] = []

    class _PatchedService:
        def reset_member_onboarding(self, guild_id, discord_user_id, display_name, actor_user_id, dry_run=False):
            called.append({'dry_run': dry_run})
            return [], 5  # 5 would-be-deleted, no new events

    monkeypatch.setattr(admin_bot, '_build_onboarding_service',
                        lambda: _PatchedService())
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    _set_operator_session(client)

    response = client.post(
        '/bot/onboarding/reset',
        json={'guild_id': 100, 'discord_user_id': 'user-1', 'dry_run': True},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['dry_run'] is True
    assert data['data']['deleted_events'] == 5
    assert called[0]['dry_run'] is True


# ---------------------------------------------------------------------------
# Role cleanup — domain
# ---------------------------------------------------------------------------

def test_request_role_cleanup_records_event():
    """request_role_cleanup appends role_cleanup_requested event."""
    svc = _make_onboarding_service()
    svc.handle_member_join(
        guild_id=100, discord_user_id='user-1', display_name='Alice')

    event = svc.request_role_cleanup(
        guild_id=100,
        discord_user_id='user-1',
        display_name='Alice',
        actor_user_id='mod1',
    )

    assert event.event_type == 'role_cleanup_requested'
    assert event.actor_user_id == 'mod1'
    assert event.discord_user_id == 'user-1'


def test_handle_onboarding_role_cleanup_command():
    """handle_onboarding_role_cleanup delegates to service."""
    svc = _make_onboarding_service()

    event = handle_onboarding_role_cleanup(
        svc,
        guild_id=100,
        discord_user_id='user-1',
        display_name='Alice',
        actor_user_id='mod1',
    )

    assert event.event_type == 'role_cleanup_requested'


def test_handle_onboarding_role_cleanup_requires_actor():
    """Empty actor_user_id raises ValueError."""
    svc = _make_onboarding_service()

    with pytest.raises(ValueError, match='actor_user_id'):
        handle_onboarding_role_cleanup(
            svc,
            guild_id=100,
            discord_user_id='user-1',
            display_name='Alice',
            actor_user_id='',
        )


def test_list_pending_role_cleanups_returns_events():
    """list_pending_role_cleanups returns role_cleanup_requested events."""
    svc = _make_onboarding_service()
    svc.request_role_cleanup(
        guild_id=100, discord_user_id='user-1', display_name='Alice', actor_user_id='mod1')
    svc.request_role_cleanup(
        guild_id=100, discord_user_id='user-2', display_name='Bob', actor_user_id='mod1')

    pending = svc.list_pending_role_cleanups(guild_id=100)

    assert len(pending) == 2
    assert all(e.event_type == 'role_cleanup_requested' for e in pending)


# ---------------------------------------------------------------------------
# E2E — role-cleanup API
# ---------------------------------------------------------------------------

def test_role_cleanup_api_records_event(client, monkeypatch):
    """POST /onboarding/role-cleanup creates cleanup event."""
    import bot_api.admin_bot as admin_bot

    called: list[dict] = []

    class _PatchedService:
        def request_role_cleanup(self, guild_id, discord_user_id, display_name, actor_user_id):
            called.append(
                {'guild_id': guild_id, 'discord_user_id': discord_user_id})
            from bot.omo_bot.models import OnboardingEvent
            from datetime import datetime, timezone
            return OnboardingEvent(
                event_id='ev-cleanup-1',
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                display_name=display_name,
                event_type='role_cleanup_requested',
                role_id=None,
                role_binding_key=None,
                idempotency_key=f'role_cleanup_requested:{guild_id}:{discord_user_id}:now',
                actor_user_id=actor_user_id,
                metadata={},
                created_at=datetime.now(timezone.utc),
            )

    monkeypatch.setattr(admin_bot, '_build_onboarding_service',
                        lambda: _PatchedService())
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    monkeypatch.setattr(admin_bot, '_record_bot_audit_event',
                        lambda **kwargs: None)
    _set_operator_session(client)

    response = client.post(
        '/bot/onboarding/role-cleanup',
        json={'guild_id': 100, 'discord_user_id': 'user-1',
              'display_name': 'Alice'},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['event_type'] == 'role_cleanup_requested'
    assert data['data']['discord_user_id'] == 'user-1'
    assert called[0]['guild_id'] == 100


def test_role_cleanup_api_requires_guild_and_user(client, monkeypatch):
    import bot_api.admin_bot as admin_bot
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    _set_operator_session(client)

    response = client.post('/bot/onboarding/role-cleanup', json={})
    assert response.status_code == 400


def test_role_cleanup_api_requires_operator_scope(client):
    response = client.post(
        '/bot/onboarding/role-cleanup',
        json={'guild_id': 100, 'discord_user_id': 'user-1'},
    )
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# E2E — diagnostics API
# ---------------------------------------------------------------------------

def test_diagnostics_api_returns_domain_summary(client, monkeypatch):
    """GET /bot/api/diagnostics returns queue, onboarding, mileage sections."""
    import bot_api.admin_bot as admin_bot
    from bot.omo_bot.models import QueueSummary
    from datetime import datetime, timezone

    dummy_summary = QueueSummary(
        queue_id='q1',
        guild_id=100,
        label='Test Queue',
        is_paused=False,
        paused_reason='',
        active_entry_id=None,
        waiting_count=2,
        total_entries=2,
        updated_at=None,
    )

    class _PatchedQueueService:
        def list_queues(self):
            return (dummy_summary,)

    class _PatchedOnboardingService:
        def list_pending_role_cleanups(self, guild_id, *, limit=50):
            return ()

    class _PatchedMileageService:
        def list_tier_stats(self, guild_id):
            return ()

    class _PatchedSettings:
        guild_id = 100
        database_url = 'postgresql://test'

    monkeypatch.setattr(admin_bot, '_load_bot_runtime_settings',
                        lambda: _PatchedSettings())
    monkeypatch.setattr(admin_bot, '_build_queue_service_from_settings',
                        lambda s: _PatchedQueueService())
    monkeypatch.setattr(admin_bot, '_build_onboarding_service',
                        lambda: _PatchedOnboardingService())
    monkeypatch.setattr(admin_bot, '_build_mileage_service_from_settings',
                        lambda s: _PatchedMileageService())
    monkeypatch.setattr(admin_bot, '_mileage_active_guild_id', lambda s: 100)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda *scopes: True)

    with client.session_transaction() as sess:
        sess[admin_bot.BOT_OPS_SESSION_KEY] = 'op-user'
        sess[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'queue.read', 'onboarding.read', 'mileage.read']
        sess[admin_bot.BOT_OPS_LOGIN_AT_KEY] = '2026-05-20T10:00:00Z'
        sess[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = '2026-05-20T10:00:00Z'

    response = client.get('/bot/api/diagnostics')

    assert response.status_code == 200
    data = response.get_json()['data']
    assert 'queues' in data
    assert data['queues']['total'] == 1
    assert data['queues']['total_waiting'] == 2
    assert 'onboarding' in data
    assert 'mileage' in data


def test_diagnostics_api_requires_scope(client):
    response = client.get('/bot/api/diagnostics')
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Permission tests — scope enforcement for all privileged moderation actions
# ---------------------------------------------------------------------------

def test_queue_remove_entry_api_requires_queue_write(client):
    response = client.post('/bot/api/queues/q1/entries/e1/remove')
    assert response.status_code in (401, 403)


def test_queue_move_entry_api_requires_queue_write(client):
    response = client.post('/bot/api/queues/q1/entries/e1/move')
    assert response.status_code in (401, 403)


def test_queue_clear_api_requires_queue_write(client):
    response = client.post('/bot/api/queues/q1/clear')
    assert response.status_code in (401, 403)


def test_mileage_adjust_api_requires_mileage_write(client):
    response = client.post('/bot/api/mileage/users/user1/adjust')
    assert response.status_code in (401, 403)


def test_mileage_reverse_api_requires_mileage_write(client):
    response = client.post('/bot/api/mileage/events/ev1/reverse')
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Audit recording tests — _record_bot_audit_event called with correct action_key
# ---------------------------------------------------------------------------

def _make_queue_api_session(client, admin_bot_module):
    """Set session with queue.write scope."""
    with client.session_transaction() as sess:
        sess[admin_bot_module.BOT_OPS_SESSION_KEY] = 'op-user'
        sess[admin_bot_module.BOT_OPS_SCOPES_SESSION_KEY] = [
            'queue.read', 'queue.write']
        sess[admin_bot_module.BOT_OPS_LOGIN_AT_KEY] = '2026-05-20T10:00:00Z'
        sess[admin_bot_module.BOT_OPS_LAST_SEEN_AT_KEY] = '2026-05-20T10:00:00Z'


def _make_mileage_api_session(client, admin_bot_module):
    with client.session_transaction() as sess:
        sess[admin_bot_module.BOT_OPS_SESSION_KEY] = 'op-user'
        sess[admin_bot_module.BOT_OPS_SCOPES_SESSION_KEY] = [
            'mileage.read', 'mileage.write']
        sess[admin_bot_module.BOT_OPS_LOGIN_AT_KEY] = '2026-05-20T10:00:00Z'
        sess[admin_bot_module.BOT_OPS_LAST_SEEN_AT_KEY] = '2026-05-20T10:00:00Z'


def _patch_queue_api(monkeypatch, admin_bot, repo):
    """Monkeypatch settings + queue repo + audit for API tests."""
    from bot.omo_bot.config import BotRuntimeSettings
    monkeypatch.setattr(admin_bot, '_load_bot_runtime_settings', lambda: BotRuntimeSettings(
        database_url='postgresql://fake', discord_token='fake', guild_id=100,
        channel_map={}, syndication_sources=[], syndication_poll_seconds=300, role_map={},
    ))
    monkeypatch.setattr(
        admin_bot, 'build_postgres_queue_repository', lambda url: repo)
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)


def test_queue_clear_api_records_audit_event(client, monkeypatch):
    """POST /api/queues/<id>/clear records queue.cleared audit event."""
    import bot_api.admin_bot as admin_bot

    repo = InMemoryQueueRepository()
    repo.save_queue(
        summary=admin_bot.QueueSummary(
            queue_id='q1', guild_id=100, label='Test', is_paused=False,
            paused_reason='', active_entry_id=None, waiting_count=0,
            total_entries=0, updated_at=None,
        ),
        entries=(),
    )

    audit_calls: list[dict] = []
    _patch_queue_api(monkeypatch, admin_bot, repo)
    monkeypatch.setattr(admin_bot, '_record_bot_audit_event',
                        lambda **kwargs: audit_calls.append(kwargs))
    _make_queue_api_session(client, admin_bot)

    response = client.post('/bot/api/queues/q1/clear',
                           json={'confirm': 'clear', 'reason': 'test'})

    assert response.status_code == 200
    assert any(c['action_key'] == 'queue.cleared' for c in audit_calls)


def test_queue_remove_entry_api_records_audit_event(client, monkeypatch):
    """POST /api/queues/<id>/entries/<entry_id>/remove records queue.entry.removed."""
    import bot_api.admin_bot as admin_bot
    from bot.omo_bot.services.queue_service import QueueService

    repo = InMemoryQueueRepository()
    svc = QueueService(repo)
    svc.ensure_queue(queue_id='q1', guild_id=100, label='Test')
    join_snap, _ = svc.join_queue(
        queue_id='q1', guild_id=100, label='Test',
        discord_user_id='user-1', display_name='Alice',
    )
    entry_id = join_snap.entries[0].entry_id

    audit_calls: list[dict] = []
    _patch_queue_api(monkeypatch, admin_bot, repo)
    monkeypatch.setattr(admin_bot, '_record_bot_audit_event',
                        lambda **kwargs: audit_calls.append(kwargs))
    _make_queue_api_session(client, admin_bot)

    response = client.post(
        f'/bot/api/queues/q1/entries/{entry_id}/remove',
        json={'reason': 'audit test'},
    )

    assert response.status_code == 200
    assert any(c['action_key'] == 'queue.entry.removed' for c in audit_calls)


def test_queue_move_entry_api_records_audit_event(client, monkeypatch):
    """POST /api/queues/<id>/entries/<entry_id>/move records queue.entry.moved."""
    import bot_api.admin_bot as admin_bot
    from bot.omo_bot.services.queue_service import QueueService

    repo = InMemoryQueueRepository()
    svc = QueueService(repo)
    svc.ensure_queue(queue_id='q1', guild_id=100, label='Test')
    for i in range(1, 4):
        svc.join_queue(
            queue_id='q1', guild_id=100, label='Test',
            discord_user_id=f'user-{i}', display_name=f'User {i}',
        )
    svc.advance_queue(queue_id='q1', actor_user_id='op')
    snap = svc.get_queue('q1')
    waiting = [e for e in snap.entries if e.state == 'waiting']
    entry_id = waiting[-1].entry_id  # last waiting entry

    audit_calls: list[dict] = []
    _patch_queue_api(monkeypatch, admin_bot, repo)
    monkeypatch.setattr(admin_bot, '_record_bot_audit_event',
                        lambda **kwargs: audit_calls.append(kwargs))
    _make_queue_api_session(client, admin_bot)

    response = client.post(
        f'/bot/api/queues/q1/entries/{entry_id}/move',
        json={'target_position': 1, 'reason': 'priority'},
    )

    assert response.status_code == 200
    assert any(c['action_key'] == 'queue.entry.moved' for c in audit_calls)


def test_mileage_adjust_api_records_audit_event(client, monkeypatch):
    """POST /api/mileage/users/<user_id>/adjust records mileage.adjusted."""
    import bot_api.admin_bot as admin_bot
    from bot.omo_bot.repositories.mileage_repo import InMemoryMileageRepository
    from bot.omo_bot.services.mileage_service import MileageService

    repo = InMemoryMileageRepository()
    svc = MileageService(repository=repo)

    from bot.omo_bot.config import BotRuntimeSettings
    monkeypatch.setattr(admin_bot, '_load_bot_runtime_settings', lambda: BotRuntimeSettings(
        database_url='postgresql://fake', discord_token='fake', guild_id=100,
        channel_map={}, syndication_sources=[], syndication_poll_seconds=300, role_map={},
    ))
    monkeypatch.setattr(admin_bot, '_mileage_active_guild_id', lambda s: 100)
    monkeypatch.setattr(
        admin_bot, '_build_mileage_service_from_settings', lambda s: svc)
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)

    audit_calls: list[dict] = []
    monkeypatch.setattr(admin_bot, '_record_bot_audit_event',
                        lambda **kwargs: audit_calls.append(kwargs))
    _make_mileage_api_session(client, admin_bot)

    response = client.post(
        '/bot/api/mileage/users/user-1/adjust',
        json={'display_name': 'Alice', 'delta': 10, 'reason': 'attendance'},
    )

    assert response.status_code == 200
    assert any(c['action_key'] == 'mileage.adjusted' for c in audit_calls)


def test_mileage_reverse_api_records_audit_event(client, monkeypatch):
    """POST /api/mileage/events/<event_id>/reverse records mileage.reversed."""
    import bot_api.admin_bot as admin_bot
    from bot.omo_bot.repositories.mileage_repo import InMemoryMileageRepository
    from bot.omo_bot.services.mileage_service import MileageService

    repo = InMemoryMileageRepository()
    svc = MileageService(repository=repo)
    _, event = svc.adjust_user_mileage(
        guild_id=100, discord_user_id='user-1', display_name='Alice',
        points_delta=5, reason='seed', actor_user_id='op',
    )
    event_id = event.event_id

    from bot.omo_bot.config import BotRuntimeSettings
    monkeypatch.setattr(admin_bot, '_load_bot_runtime_settings', lambda: BotRuntimeSettings(
        database_url='postgresql://fake', discord_token='fake', guild_id=100,
        channel_map={}, syndication_sources=[], syndication_poll_seconds=300, role_map={},
    ))
    monkeypatch.setattr(admin_bot, '_mileage_active_guild_id', lambda s: 100)
    monkeypatch.setattr(
        admin_bot, '_build_mileage_service_from_settings', lambda s: svc)
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)

    audit_calls: list[dict] = []
    monkeypatch.setattr(admin_bot, '_record_bot_audit_event',
                        lambda **kwargs: audit_calls.append(kwargs))
    _make_mileage_api_session(client, admin_bot)

    response = client.post(
        f'/bot/api/mileage/events/{event_id}/reverse',
        json={'reason': 'correcting error'},
    )

    assert response.status_code == 200
    assert any(c['action_key'] == 'mileage.reversed' for c in audit_calls)


def test_onboarding_reset_api_records_audit_event(client, monkeypatch):
    """POST /onboarding/reset records onboarding.reset via audit service."""
    import bot_api.admin_bot as admin_bot

    audit_records: list[dict] = []

    class _PatchedAuditService:
        def record(self, **kwargs):
            audit_records.append(kwargs)

    class _PatchedService:
        def reset_member_onboarding(self, guild_id, discord_user_id, display_name, actor_user_id, dry_run=False):
            from bot.omo_bot.models import OnboardingEvent
            from datetime import datetime, timezone
            marker = OnboardingEvent(
                event_id='ev-1', guild_id=guild_id, discord_user_id=discord_user_id,
                display_name=display_name, event_type='reset', role_id=None,
                role_binding_key=None, idempotency_key='k1', actor_user_id=actor_user_id,
                metadata={}, created_at=datetime.now(timezone.utc),
            )
            return [marker], 2

    monkeypatch.setattr(admin_bot, '_build_onboarding_service',
                        lambda: _PatchedService())
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service',
                        lambda: _PatchedAuditService())
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    _set_operator_session(client)

    response = client.post(
        '/bot/onboarding/reset',
        json={'guild_id': 100, 'discord_user_id': 'user-1', 'confirm': 'reset'},
    )

    assert response.status_code == 200
    assert any(r.get('action_key') ==
               'onboarding.reset' for r in audit_records)
