"""E2E API tests for moderation endpoints.

Covers:
- Control-room onboarding reset API
- Role-cleanup API
- Diagnostics API
- Permission / scope enforcement
- Audit recording integration
"""

from __future__ import annotations

import pytest

from bot.omo_bot.models.queue import QueueSummary
from bot.omo_bot.repositories.mileage_repo import InMemoryMileageRepository
from bot.omo_bot.repositories.queue_repo import InMemoryQueueRepository


# ---------------------------------------------------------------------------
# Fixtures
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


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _set_operator_session(client):
    import bot_api.admin_bot as admin_bot
    with client.session_transaction() as sess:
        sess[admin_bot.BOT_OPS_SESSION_KEY] = 'op-user'
        sess[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'onboarding.read', 'onboarding.write']
        sess[admin_bot.BOT_OPS_LOGIN_AT_KEY] = '2026-05-20T10:00:00Z'
        sess[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = '2026-05-20T10:00:00Z'


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


# ---------------------------------------------------------------------------
# E2E — control_room reset_onboarding_api
# ---------------------------------------------------------------------------

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

def test_queue_remove_api_records_audit_event(client, monkeypatch):
    """POST /api/queues/<id>/entries/<eid>/remove records entry_removed audit event."""
    import bot_api.admin_bot as admin_bot

    repo = InMemoryQueueRepository()
    from bot.omo_bot.models.queue import QueueSummary
    repo.save_queue(
        summary=QueueSummary(
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

    response = client.post(
        '/bot/api/queues/q1/entries/e1/remove',
        json={'reason': 'test'},
    )

    assert response.status_code == 200
    assert any(call.get('action_key') == 'entry_removed'
               for call in audit_calls)


def test_queue_move_api_records_audit_event(client, monkeypatch):
    """POST /api/queues/<id>/entries/<eid>/move records entry_moved audit event."""
    import bot_api.admin_bot as admin_bot

    repo = InMemoryQueueRepository()
    from bot.omo_bot.models.queue import QueueSummary
    repo.save_queue(
        summary=QueueSummary(
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

    response = client.post(
        '/bot/api/queues/q1/entries/e1/move',
        json={'target_position': 1, 'reason': 'test'},
    )

    assert response.status_code == 200
    assert any(call.get('action_key') == 'entry_moved'
               for call in audit_calls)


def test_queue_clear_api_records_audit_event(client, monkeypatch):
    """POST /api/queues/<id>/clear records queue.cleared audit event."""
    import bot_api.admin_bot as admin_bot

    from bot.omo_bot.models.queue import QueueSummary
    repo = InMemoryQueueRepository()
    repo.save_queue(
        summary=QueueSummary(
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
    assert any(call.get('action_key') == 'queue_cleared'
               for call in audit_calls)


def test_mileage_adjust_api_records_audit_event(client, monkeypatch):
    """POST /api/mileage/users/<id>/adjust records mileage.adjusted audit event."""
    import bot_api.admin_bot as admin_bot
    from bot.omo_bot.config import BotRuntimeSettings

    audit_calls: list[dict] = []
    monkeypatch.setattr(admin_bot, '_load_bot_runtime_settings', lambda: BotRuntimeSettings(
        database_url='postgresql://fake', discord_token='fake', guild_id=100,
        channel_map={}, syndication_sources=[], syndication_poll_seconds=300, role_map={},
    ))
    monkeypatch.setattr(
        admin_bot, 'build_postgres_mileage_repository', lambda url: InMemoryMileageRepository())
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    monkeypatch.setattr(admin_bot, '_record_bot_audit_event',
                        lambda **kwargs: audit_calls.append(kwargs))
    _make_mileage_api_session(client, admin_bot)

    response = client.post(
        '/bot/api/mileage/users/user1/adjust',
        json={'points_delta': 10, 'reason': 'test'},
    )

    assert response.status_code == 200
    assert any(call.get('action_key') == 'mileage.adjusted'
               for call in audit_calls)


def test_mileage_reverse_api_records_audit_event(client, monkeypatch):
    """POST /api/mileage/events/<id>/reverse records mileage.reversed audit event."""
    import bot_api.admin_bot as admin_bot
    from bot.omo_bot.config import BotRuntimeSettings

    audit_calls: list[dict] = []
    monkeypatch.setattr(admin_bot, '_load_bot_runtime_settings', lambda: BotRuntimeSettings(
        database_url='postgresql://fake', discord_token='fake', guild_id=100,
        channel_map={}, syndication_sources=[], syndication_poll_seconds=300, role_map={},
    ))
    monkeypatch.setattr(
        admin_bot, 'build_postgres_mileage_repository', lambda url: InMemoryMileageRepository())
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    monkeypatch.setattr(admin_bot, '_record_bot_audit_event',
                        lambda **kwargs: audit_calls.append(kwargs))
    _make_mileage_api_session(client, admin_bot)

    response = client.post(
        '/bot/api/mileage/events/ev1/reverse',
        json={'reason': 'test'},
    )

    assert response.status_code == 200
    assert any(call.get('action_key') == 'mileage.reversed'
               for call in audit_calls)
