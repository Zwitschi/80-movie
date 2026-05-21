"""Onboarding domain unit tests and E2E tests for control_room API."""

import pytest
from datetime import datetime, timezone

from bot.omo_bot.models import OnboardingConfig, OnboardingRoleBinding
from bot.omo_bot.repositories.onboarding_repo import InMemoryOnboardingRepository
from bot.omo_bot.services.onboarding_service import OnboardingService


# ---------------------------------------------------------------------------
# Unit tests — OnboardingService domain logic
# ---------------------------------------------------------------------------

def _make_service():
    return OnboardingService(onboarding_repository=InMemoryOnboardingRepository())


def test_onboarding_handle_member_join_happy_path():
    svc = _make_service()
    config = OnboardingConfig(
        guild_id=100,
        welcome_copy='Welcome to the server!',
        starter_channel_ids=(111, 222),
        role_bindings=(
            OnboardingRoleBinding(binding_key='member',
                                  role_id=999, label='Member'),
        ),
    )
    svc.save_config(config)

    events, was_duplicate = svc.handle_member_join(
        guild_id=100,
        discord_user_id='user-1',
        display_name='Alice',
    )

    assert not was_duplicate
    event_types = {e.event_type for e in events}
    assert 'member_joined' in event_types
    assert 'role_assigned' in event_types
    assert 'welcome_sent' in event_types
    assert len(events) == 3  # join + 1 role + welcome

    role_event = next(e for e in events if e.event_type == 'role_assigned')
    assert role_event.role_id == 999
    assert role_event.role_binding_key == 'member'


def test_onboarding_handle_member_join_duplicate_protection():
    svc = _make_service()
    config = OnboardingConfig(
        guild_id=100,
        welcome_copy='Hi!',
        starter_channel_ids=(),
        role_bindings=(),
    )
    svc.save_config(config)

    events1, dup1 = svc.handle_member_join(100, 'user-2', 'Bob')
    assert not dup1
    assert len(events1) == 2  # join + welcome (no roles)

    # Second call for same user should be a no-op
    events2, dup2 = svc.handle_member_join(100, 'user-2', 'Bob')
    assert dup2
    assert events2 == []


def test_onboarding_handle_member_join_no_config():
    svc = _make_service()
    # No config saved — still records join event, skips role/welcome
    events, was_duplicate = svc.handle_member_join(100, 'user-3', 'Carol')
    assert not was_duplicate
    assert len(events) == 1
    assert events[0].event_type == 'member_joined'


def test_onboarding_replay_adds_missing_events():
    svc = _make_service()
    config = OnboardingConfig(
        guild_id=100,
        welcome_copy='Welcome back!',
        starter_channel_ids=(333,),
        role_bindings=(
            OnboardingRoleBinding(binding_key='vip', role_id=888, label='VIP'),
        ),
    )
    svc.save_config(config)

    # First join — only records the join event (simulate partial failure by
    # using raw repo to insert only the join idempotency key)
    repo = svc._repo
    from bot.omo_bot.models import OnboardingEvent
    import uuid
    join_event = OnboardingEvent(
        event_id=str(uuid.uuid4()),
        guild_id=100,
        discord_user_id='user-4',
        display_name='Dave',
        event_type='member_joined',
        role_id=None,
        role_binding_key=None,
        idempotency_key='member_joined:100:user-4',
        actor_user_id=None,
        metadata={},
        created_at=datetime.now(tz=timezone.utc),
    )
    repo.append_event(join_event)

    # Replay should fill in the missing role + welcome events
    events, was_skipped = svc.replay_member_onboarding(
        guild_id=100,
        discord_user_id='user-4',
        display_name='Dave',
        actor_user_id='operator-1',
    )
    assert not was_skipped
    event_types = {e.event_type for e in events}
    assert 'role_assigned' in event_types
    assert 'welcome_sent' in event_types
    assert 'replay' in event_types


def test_onboarding_replay_skipped_when_already_complete():
    svc = _make_service()
    config = OnboardingConfig(
        guild_id=100,
        welcome_copy='Hi!',
        starter_channel_ids=(),
        role_bindings=(),
    )
    svc.save_config(config)

    svc.handle_member_join(100, 'user-5', 'Eve')

    events, was_skipped = svc.replay_member_onboarding(
        guild_id=100,
        discord_user_id='user-5',
        display_name='Eve',
        actor_user_id='op',
    )
    assert was_skipped
    assert events == []


def test_onboarding_list_events():
    svc = _make_service()
    config = OnboardingConfig(
        guild_id=200,
        welcome_copy='Welcome!',
        starter_channel_ids=(),
        role_bindings=(),
    )
    svc.save_config(config)

    svc.handle_member_join(200, 'u1', 'Alice')
    svc.handle_member_join(200, 'u2', 'Bob')

    events = svc.list_recent_events(200)
    user_ids = {e.discord_user_id for e in events}
    assert 'u1' in user_ids
    assert 'u2' in user_ids


# ---------------------------------------------------------------------------
# E2E tests — control_room API endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from control_room.app import create_app as create_control_room_app
    app = create_control_room_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_onboarding_events_and_replay_via_api(client, monkeypatch):
    from bot.omo_bot.config import BotRuntimeSettings
    from bot.omo_bot.repositories.onboarding_repo import InMemoryOnboardingRepository
    from bot.omo_bot.services.onboarding_service import OnboardingService
    from bot.omo_bot.models import OnboardingConfig, OnboardingRoleBinding
    from control_room import admin_bot

    repo = InMemoryOnboardingRepository()
    svc = OnboardingService(onboarding_repository=repo)

    # Pre-populate config
    config = OnboardingConfig(
        guild_id=111,
        welcome_copy='Hello!',
        starter_channel_ids=(555,),
        role_bindings=(
            OnboardingRoleBinding(binding_key='member',
                                  role_id=777, label='Member'),
        ),
    )
    svc.save_config(config)

    def mock_load_settings():
        return BotRuntimeSettings(
            database_url='postgresql://fake',
            discord_token='fake',
            guild_id=111,
            channel_map={},
            syndication_sources=[],
            syndication_poll_seconds=300,
            role_map={},
        )

    def mock_build_onboarding_repo(_url):
        return repo

    monkeypatch.setattr(
        admin_bot, '_load_bot_runtime_settings', mock_load_settings)
    monkeypatch.setattr(
        admin_bot, 'build_postgres_onboarding_repository', mock_build_onboarding_repo)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service', lambda: None)

    with client.session_transaction() as sess:
        sess[admin_bot.BOT_OPS_SESSION_KEY] = 'op-user'
        sess[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'onboarding.read', 'onboarding.write']
        sess[admin_bot.BOT_OPS_LOGIN_AT_KEY] = '2026-05-20T10:00:00Z'
        sess[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = '2026-05-20T10:00:00Z'

    # 1. List events — should be empty initially
    resp = client.get('/bot/onboarding/events?guild_id=111')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['data'] == []
    assert data['meta']['count'] == 0

    # 2. Simulate a member join via service
    svc.handle_member_join(111, 'discord-user-42', 'Alice')

    # 3. List events — should now have join + role + welcome
    resp = client.get('/bot/onboarding/events?guild_id=111')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['meta']['count'] == 3
    event_types = {e['event_type'] for e in data['data']}
    assert 'member_joined' in event_types
    assert 'role_assigned' in event_types
    assert 'welcome_sent' in event_types

    # 4. Replay for a different user who was never joined
    resp = client.post('/bot/onboarding/replay', json={
        'guild_id': 111,
        'discord_user_id': 'discord-user-99',
        'display_name': 'NewMember',
    })
    assert resp.status_code == 200
    result = resp.get_json()
    assert result['data']['skipped'] is False
    assert result['data']['replayed_events'] > 0

    # 5. Replay again — should be skipped (already complete)
    resp = client.post('/bot/onboarding/replay', json={
        'guild_id': 111,
        'discord_user_id': 'discord-user-99',
        'display_name': 'NewMember',
    })
    assert resp.status_code == 200
    result = resp.get_json()
    assert result['data']['skipped'] is True
    assert result['data']['replayed_events'] == 0

