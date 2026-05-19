from datetime import datetime, timedelta, timezone
from typing import cast
from urllib.parse import parse_qs, urlparse

from website.app import create_app
from website.movie_site import admin_bot
from website.movie_site import bot_operator_repo
from website.movie_site import bot_operator_service
from bot.omo_bot.config import BotRuntimeSettings
from bot.omo_bot.models import SyndicationFetchResult, SyndicationItem
from bot.omo_bot.repositories import InMemoryBotAuditLogRepository, InMemoryBotConfigRepository, InMemoryMileageRepository, InMemoryQueueRepository, InMemorySyndicationSourceRepository
from bot.omo_bot.models import SyndicationSourceState
from bot.omo_bot.services import MileageService, QueueService


def test_admin_bot_overview_renders_in_testing_mode():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/admin/bot')

    assert response.status_code == 200
    assert b'Bot Overview' in response.data
    assert b'Component Snapshot' in response.data


def test_admin_bot_health_api_returns_snapshot_in_testing_mode():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/admin/bot/api/health')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['status'] in {'ok', 'degraded'}
    assert 'components' in payload['data']
    assert 'database' in payload['data']['components']
    assert payload['data']['links']['health'].endswith('/admin/bot/api/health')


def test_admin_bot_health_page_renders_syndication_summary(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    repository = InMemorySyndicationSourceRepository(
        [
            SyndicationSourceState(
                source_key='youtube',
                checkpoint='video-123',
                last_failed_at=datetime(
                    2026, 5, 18, 12, 0, tzinfo=timezone.utc),
            )
        ]
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: repository,
    )

    response = client.get('/admin/bot/health')

    assert response.status_code == 200
    assert b'Syndication Status' in response.data
    assert b'Attention sources' in response.data


def test_admin_bot_services_api_returns_component_details():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/admin/bot/api/health/services')

    assert response.status_code == 200
    payload = response.get_json()
    assert 'website_app' in payload['data']
    assert 'jobs' in payload['data']


def test_admin_bot_page_redirects_without_operator_session_when_not_testing():
    app = create_app()
    client = app.test_client()

    response = client.get('/admin/bot')

    assert response.status_code == 302
    assert '/admin/bot/login' in response.headers['Location']


def test_admin_bot_api_requires_operator_session_when_not_testing():
    app = create_app()
    client = app.test_client()

    response = client.get('/admin/bot/api/health')

    assert response.status_code == 401
    payload = response.get_json()
    assert payload['error']['code'] == 'operator_auth_required'


def test_admin_bot_oauth_start_redirects_and_sets_state():
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/admin/bot/oauth/callback',
    )
    client = app.test_client()

    response = client.get('/admin/bot/oauth/start?next=/admin/bot/health')

    assert response.status_code == 302
    location = response.headers['Location']
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.netloc == 'discord.com'
    assert query['client_id'] == ['client-id']
    assert query['redirect_uri'] == [
        'https://example.com/admin/bot/oauth/callback']
    assert query['scope'] == ['identify']

    with client.session_transaction() as flask_session:
        assert flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY]
        assert flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] == '/admin/bot/health'


def test_admin_bot_oauth_start_uses_env_driven_config(monkeypatch):
    monkeypatch.setenv('OMO_DISCORD_CLIENT_ID', 'env-client-id')
    monkeypatch.setenv('OMO_DISCORD_CLIENT_SECRET', 'env-client-secret')
    monkeypatch.setenv(
        'OMO_DISCORD_REDIRECT_URI',
        'https://example.com/admin/bot/oauth/callback',
    )

    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/admin/bot/oauth/start?next=/admin/bot/health')

    assert response.status_code == 302
    location = response.headers['Location']
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert query['client_id'] == ['env-client-id']
    assert query['redirect_uri'] == [
        'https://example.com/admin/bot/oauth/callback']


def test_admin_bot_oauth_callback_rejects_state_mismatch():
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/admin/bot/oauth/callback',
    )
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'

    response = client.get(
        '/admin/bot/oauth/callback?state=wrong-state&code=test-code')

    assert response.status_code == 400
    assert b'OAuth state did not match' in response.data


def test_discord_oauth_callback_alias_is_reachable(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://admin.openmicodyssey.com/oauth/discord/callback',
        BOT_OPS_ALLOWED_USER_IDS=('123456',),
        BOT_OPS_DEFAULT_SCOPES=('ops.read',),
    )
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        'exchange_code_for_discord_identity',
        lambda code: {'user_id': '123456',
                      'username': 'operator', 'global_name': 'Operator'},
    )
    monkeypatch.setattr(
        bot_operator_service,
        'get_operator_access',
        lambda user_id: {'allowed': True, 'scopes': [
            'ops.read'], 'operator_record': None},
    )
    monkeypatch.setattr(
        bot_operator_service,
        'persist_operator_login',
        lambda **kwargs: None,
    )

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'
        flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] = '/admin/bot/health'

    response = client.get(
        '/oauth/discord/callback?state=expected-state&code=test-code')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/bot/health')


def test_admin_bot_oauth_callback_sets_operator_session_for_allowed_user(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/admin/bot/oauth/callback',
        BOT_OPS_ALLOWED_USER_IDS=('123456',),
        BOT_OPS_DEFAULT_SCOPES=('ops.read', 'queue.write'),
    )
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        'exchange_code_for_discord_identity',
        lambda code: {'user_id': '123456',
                      'username': 'operator', 'global_name': 'Operator'},
    )
    monkeypatch.setattr(
        bot_operator_service,
        'get_operator_access',
        lambda user_id: {'allowed': True, 'scopes': [
            'ops.read', 'queue.write'], 'operator_record': None},
    )
    monkeypatch.setattr(
        bot_operator_service,
        'persist_operator_login',
        lambda **kwargs: None,
    )

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'
        flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] = '/admin/bot/health'

    response = client.get(
        '/admin/bot/oauth/callback?state=expected-state&code=test-code')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/bot/health')
    with client.session_transaction() as flask_session:
        assert flask_session[admin_bot.BOT_OPS_SESSION_KEY] == '123456'
        assert flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] == [
            'ops.read', 'queue.write']
        assert admin_bot.BOT_OPS_OAUTH_STATE_KEY not in flask_session


def test_admin_bot_oauth_callback_rejects_disallowed_operator(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/admin/bot/oauth/callback',
        BOT_OPS_ALLOWED_USER_IDS=('999999',),
    )
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        'exchange_code_for_discord_identity',
        lambda code: {'user_id': '123456',
                      'username': 'operator', 'global_name': 'Operator'},
    )
    monkeypatch.setattr(
        bot_operator_service,
        'get_operator_access',
        lambda user_id: {'allowed': False, 'scopes': [
            'ops.read'], 'operator_record': None},
    )

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'

    response = client.get(
        '/admin/bot/oauth/callback?state=expected-state&code=test-code')

    assert response.status_code == 403
    assert b'not on the control-room allowlist' in response.data


def test_admin_bot_oauth_callback_accepts_db_backed_operator_record(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/admin/bot/oauth/callback',
        BOT_OPS_ALLOWED_USER_IDS=(),
        BOT_OPS_DEFAULT_SCOPES=('ops.read',),
    )
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        'exchange_code_for_discord_identity',
        lambda code: {'user_id': 'db-user',
                      'username': 'operator', 'global_name': 'Operator'},
    )
    monkeypatch.setattr(
        bot_operator_service,
        'get_operator_access',
        lambda user_id: {
            'allowed': user_id == 'db-user',
            'scopes': ['ops.read', 'syndication.write'],
            'operator_record': {'discord_user_id': user_id},
        },
    )
    monkeypatch.setattr(
        bot_operator_service,
        'persist_operator_login',
        lambda **kwargs: None,
    )

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'
        flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] = '/admin/bot/health'

    response = client.get(
        '/admin/bot/oauth/callback?state=expected-state&code=test-code')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/bot/health')
    with client.session_transaction() as flask_session:
        assert flask_session[admin_bot.BOT_OPS_SESSION_KEY] == 'db-user'
        assert flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] == [
            'ops.read', 'syndication.write']


def test_admin_bot_oauth_callback_persists_operator_profile_metadata(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/admin/bot/oauth/callback',
        BOT_OPS_ALLOWED_USER_IDS=('123456',),
        BOT_OPS_DEFAULT_SCOPES=('ops.read', 'queue.write'),
    )
    client = app.test_client()
    persisted: dict[str, object] = {}

    monkeypatch.setattr(
        admin_bot,
        'exchange_code_for_discord_identity',
        lambda code: {
            'user_id': '123456',
            'username': 'operator',
            'global_name': 'Operator Name',
            'avatar_url': 'https://cdn.example/avatar.png',
        },
    )
    monkeypatch.setattr(
        bot_operator_service,
        'get_operator_access',
        lambda user_id: {'allowed': True, 'scopes': [
            'ops.read', 'queue.write'], 'operator_record': None},
    )
    monkeypatch.setattr(
        bot_operator_service,
        'persist_operator_login',
        lambda **kwargs: persisted.update(kwargs),
    )

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'
        flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] = '/admin/bot/health'

    response = client.get(
        '/admin/bot/oauth/callback?state=expected-state&code=test-code')

    assert response.status_code == 302
    operator_identity = cast(dict[str, object], persisted['operator_identity'])
    assert operator_identity['user_id'] == '123456'
    assert operator_identity['username'] == 'operator'
    assert operator_identity['global_name'] == 'Operator Name'
    assert operator_identity['avatar_url'] == 'https://cdn.example/avatar.png'
    assert persisted['scopes'] == ['ops.read', 'queue.write']
    assert persisted['last_login_at']


def test_admin_bot_logout_clears_only_operator_session_keys():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SESSION_ID_KEY] = 'session-id'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.read']
        flask_session[admin_bot.BOT_OPS_LOGIN_AT_KEY] = datetime.now(
            timezone.utc).isoformat()
        flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = datetime.now(
            timezone.utc).isoformat()
        flask_session['editorial_marker'] = 'keep-me'

    response = client.post('/admin/bot/logout')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/bot/login')
    with client.session_transaction() as flask_session:
        assert admin_bot.BOT_OPS_SESSION_KEY not in flask_session
        assert admin_bot.BOT_OPS_SESSION_ID_KEY not in flask_session
        assert flask_session['editorial_marker'] == 'keep-me'


def test_admin_bot_page_redirects_when_operator_session_is_idle_timed_out():
    app = create_app()
    app.config['BOT_OPS_SESSION_IDLE_MINUTES'] = 5
    client = app.test_client()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = stale

    response = client.get('/admin/bot')

    assert response.status_code == 302
    assert 'error=session-expired' in response.headers['Location']
    with client.session_transaction() as flask_session:
        assert admin_bot.BOT_OPS_SESSION_KEY not in flask_session


def test_admin_bot_api_returns_session_expired_for_idle_timeout():
    app = create_app()
    app.config['BOT_OPS_SESSION_IDLE_MINUTES'] = 5
    client = app.test_client()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = stale

    response = client.get('/admin/bot/api/health')

    assert response.status_code == 401
    payload = response.get_json()
    assert payload['error']['code'] == 'operator_session_expired'


def test_admin_bot_authenticated_request_refreshes_last_seen():
    app = create_app()
    app.config['BOT_OPS_SESSION_IDLE_MINUTES'] = 60
    client = app.test_client()
    older = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = older

    response = client.get('/admin/bot/health')

    assert response.status_code == 200
    with client.session_transaction() as flask_session:
        refreshed = flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY]
        assert refreshed != older


def test_admin_bot_operators_page_renders_list(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        bot_operator_repo,
        'list_bot_operators',
        lambda: [
            {
                'discord_user_id': '123456',
                'username': 'operator',
                'global_name': 'Operator Name',
                'avatar_url': None,
                'scopes': ['ops.read', 'queue.write'],
                'is_active': True,
                'last_login_at': '2026-05-18T12:00:00+00:00',
            }
        ],
    )

    response = client.get('/admin/bot/operators')

    assert response.status_code == 200
    assert b'Bot Operators' in response.data
    assert b'Operator Name' in response.data
    assert b'queue.write' in response.data


def test_admin_bot_operators_api_returns_records(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        bot_operator_repo,
        'list_bot_operators',
        lambda: [
            {
                'discord_user_id': '123456',
                'username': 'operator',
                'global_name': 'Operator Name',
                'avatar_url': None,
                'scopes': ['ops.read'],
                'is_active': True,
                'last_login_at': None,
            }
        ],
    )

    response = client.get('/admin/bot/api/operators')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data'][0]['discord_user_id'] == '123456'


def test_admin_bot_queues_page_renders_queue_summary(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'queue': 100},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    queue_repository = InMemoryQueueRepository()
    queue_service = QueueService(queue_repository)
    queue_service.join_queue(
        queue_id='guild-1:open-mic',
        guild_id=1,
        label='Open Mic',
        discord_user_id='u1',
        display_name='Alpha',
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_queue_repository',
        lambda database_url: queue_repository,
    )

    response = client.get('/admin/bot/queues')

    assert response.status_code == 200
    assert b'Bot Queues' in response.data
    assert b'Open Mic' in response.data
    assert b'guild-1:open-mic' in response.data


def test_admin_bot_advance_queue_api_updates_snapshot_and_emits_audit_entry(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SESSION_ID_KEY] = 'session-1'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['queue.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'queue': 100},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    queue_repository = InMemoryQueueRepository()
    queue_service = QueueService(queue_repository)
    queue_service.join_queue(
        queue_id='guild-1:open-mic',
        guild_id=1,
        label='Open Mic',
        discord_user_id='u1',
        display_name='Alpha',
    )
    queue_service.join_queue(
        queue_id='guild-1:open-mic',
        guild_id=1,
        label='Open Mic',
        discord_user_id='u2',
        display_name='Beta',
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_queue_repository',
        lambda database_url: queue_repository,
    )
    audit_repository = InMemoryBotAuditLogRepository()
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: audit_repository,
    )

    response = client.post('/admin/bot/api/queues/guild-1:open-mic/advance')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['event']['event_type'] == 'queue_advanced'
    assert payload['data']['summary']['active_entry_id'] is not None
    assert payload['data']['entries'][0]['state'] == 'active'
    assert len(audit_repository.entries) == 1
    assert audit_repository.entries[0].action_key == 'queue.advanced'


def test_admin_bot_mileage_page_renders_user_summary_and_tiers(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'queue': 100},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    mileage_repository = InMemoryMileageRepository()
    mileage_service = MileageService(mileage_repository)
    mileage_service.upsert_tier(
        guild_id=987654321, name='Bronze', points_required=10, sort_order=1)
    mileage_service.adjust_user_mileage(
        guild_id=987654321,
        discord_user_id='u1',
        display_name='Alpha',
        points_delta=12,
        reason='Hosted event',
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_mileage_repository',
        lambda database_url: mileage_repository,
    )

    response = client.get('/admin/bot/mileage')

    assert response.status_code == 200
    assert b'Mileage / XP' in response.data
    assert b'Alpha' in response.data
    assert b'Bronze' in response.data


def test_admin_bot_adjust_mileage_user_api_updates_total_and_emits_audit_entry(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SESSION_ID_KEY] = 'session-1'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['mileage.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'queue': 100},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    mileage_repository = InMemoryMileageRepository()
    mileage_service = MileageService(mileage_repository)
    mileage_service.upsert_tier(
        guild_id=987654321, name='Bronze', points_required=10, sort_order=1)
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_mileage_repository',
        lambda database_url: mileage_repository,
    )
    audit_repository = InMemoryBotAuditLogRepository()
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: audit_repository,
    )

    response = client.post(
        '/admin/bot/api/mileage/users/u1/adjust',
        json={
            'display_name': 'Alpha',
            'delta': 12,
            'reason': 'Hosted event',
            'correlation_id': 'adjust-1',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['event']['event_type'] == 'manual_adjustment'
    assert payload['data']['total']['total_points'] == 12
    assert len(audit_repository.entries) == 1
    assert audit_repository.entries[0].action_key == 'mileage.adjusted'


def test_admin_bot_reverse_mileage_event_api_appends_reversal_and_audit(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SESSION_ID_KEY] = 'session-1'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['mileage.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'queue': 100},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    mileage_repository = InMemoryMileageRepository()
    mileage_service = MileageService(mileage_repository)
    event_detail, original_event = mileage_service.adjust_user_mileage(
        guild_id=987654321,
        discord_user_id='u1',
        display_name='Alpha',
        points_delta=9,
        reason='Volunteer shift',
        actor_user_id='operator-1',
    )
    assert event_detail.total.total_points == 9
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_mileage_repository',
        lambda database_url: mileage_repository,
    )
    audit_repository = InMemoryBotAuditLogRepository()
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: audit_repository,
    )

    response = client.post(
        f'/admin/bot/api/mileage/events/{original_event.event_id}/reverse',
        json={'reason': 'Duplicate credit'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['event']['event_type'] == 'manual_reversal'
    assert payload['data']['total']['total_points'] == 0
    assert len(audit_repository.entries) == 1
    assert audit_repository.entries[0].action_key == 'mileage.reversed'


def test_admin_bot_syndication_page_renders_configured_sources(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    repository = InMemorySyndicationSourceRepository(
        [
            SyndicationSourceState(
                source_key='youtube',
                checkpoint='video-123',
            )
        ]
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: repository,
    )

    response = client.get('/admin/bot/syndication')

    assert response.status_code == 200
    assert b'Configured Sources' in response.data
    assert b'Last poll result' in response.data
    assert b'youtube' in response.data
    assert b'video-123' in response.data
    assert b'announcements' in response.data


def test_admin_bot_syndication_page_renders_retry_controls_for_writer(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'syndication.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: InMemorySyndicationSourceRepository(
            [SyndicationSourceState(
                source_key='youtube', checkpoint='video-123')]
        ),
    )

    response = client.get('/admin/bot/syndication')

    assert response.status_code == 200
    assert b'Retry poll' in response.data
    assert b'Reset checkpoint' in response.data


def test_admin_bot_syndication_sources_api_returns_snapshot(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=None,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    repository = InMemorySyndicationSourceRepository(
        [
            SyndicationSourceState(
                source_key='youtube',
                checkpoint='video-123',
            )
        ]
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: repository,
    )

    response = client.get('/admin/bot/api/syndication/sources')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['status'] == 'ok'
    assert payload['data'][0]['source_key'] == 'youtube'
    assert payload['data'][0]['checkpoint'] == 'video-123'


def test_admin_bot_syndication_channels_api_returns_bindings(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=None,
            channel_map={'announcements': 200, 'queue': 100},
            database_url=None,
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )

    response = client.get('/admin/bot/api/syndication/channels')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['status'] == 'ok'
    assert payload['data'] == [
        {'binding_key': 'announcements', 'channel_id': 200},
        {'binding_key': 'queue', 'channel_id': 100},
    ]


def test_admin_bot_config_page_renders_sources_and_channel_bindings(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=None,
            channel_map={'announcements': 200, 'queue': 100},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: InMemorySyndicationSourceRepository(
            [SyndicationSourceState(
                source_key='youtube', checkpoint='video-123')]
        ),
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_config_repository',
        lambda database_url: InMemoryBotConfigRepository(
            guild_id=987654321,
            channel_map={'announcements': 200, 'queue': 100},
            role_map={'moderator': 300},
        ),
    )

    response = client.get('/admin/bot/config')

    assert response.status_code == 200
    assert b'Runtime Configuration' in response.data
    assert b'Syndication Sources' in response.data
    assert b'Channel Bindings' in response.data
    assert b'Role Bindings' in response.data
    assert b'announcements' in response.data
    assert b'moderator' in response.data


def test_admin_bot_config_api_returns_repository_managed_bindings(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=111,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: InMemorySyndicationSourceRepository(),
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_config_repository',
        lambda database_url: InMemoryBotConfigRepository(
            guild_id=222,
            channel_map={'queue': 300},
            role_map={'moderator': 400},
        ),
    )

    response = client.get('/admin/bot/api/config')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['guild_config']['guild_id'] == 222
    assert payload['data']['channel_bindings'][0]['binding_key'] == 'queue'
    assert payload['data']['channel_bindings'][0]['channel_id'] == 300
    assert payload['data']['role_bindings'][0]['binding_key'] == 'moderator'
    assert payload['data']['role_bindings'][0]['role_id'] == 400


def test_admin_bot_upsert_channel_binding_api_updates_repository(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'syndication.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=222,
            channel_map={},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: InMemorySyndicationSourceRepository(),
    )
    repository = InMemoryBotConfigRepository(guild_id=222)
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_config_repository',
        lambda database_url: repository,
    )

    response = client.post(
        '/admin/bot/api/config/channels',
        json={'binding_key': 'announcements', 'channel_id': 200},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['binding_key'] == 'announcements'
    assert payload['data']['channel_id'] == 200
    assert repository.list_channel_bindings(222) == [
        {'guild_id': 222, 'binding_key': 'announcements', 'channel_id': 200}
    ]


def test_admin_bot_disable_syndication_source_api_updates_enabled_state(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'syndication.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=None,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    repository = InMemorySyndicationSourceRepository(
        [SyndicationSourceState(source_key='youtube',
                                enabled=True, checkpoint='video-123')]
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: repository,
    )

    response = client.post('/admin/bot/api/config/sources/youtube/disable')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['enabled'] is False


def test_admin_bot_disable_syndication_source_api_emits_audit_entry(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SESSION_ID_KEY] = 'session-1'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'syndication.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=None,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    repository = InMemorySyndicationSourceRepository(
        [SyndicationSourceState(source_key='youtube',
                                enabled=True, checkpoint='video-123')]
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: repository,
    )
    audit_repository = InMemoryBotAuditLogRepository()
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: audit_repository,
    )

    response = client.post('/admin/bot/api/config/sources/youtube/disable')

    assert response.status_code == 200
    assert len(audit_repository.entries) == 1
    entry = audit_repository.entries[0]
    assert entry.action_key == 'syndication.source.disabled'
    assert entry.target_key == 'youtube'
    assert entry.actor_user_id == '123456'
    assert entry.before_state == {
        'source_key': 'youtube',
        'enabled': True,
        'checkpoint': 'video-123',
        'last_polled_at': None,
        'last_succeeded_at': None,
        'last_failed_at': None,
    }
    assert entry.after_state == {
        'source_key': 'youtube',
        'enabled': False,
        'checkpoint': 'video-123',
        'last_polled_at': None,
        'last_succeeded_at': None,
        'last_failed_at': None,
    }


def test_admin_bot_commands_page_renders_poll_all_command(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'syndication.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=None,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: InMemorySyndicationSourceRepository(
            [SyndicationSourceState(
                source_key='youtube', checkpoint='video-123')]
        ),
    )

    response = client.get('/admin/bot/commands')

    assert response.status_code == 200
    assert b'Command Actions' in response.data
    assert b'Poll all sources now' in response.data


def test_admin_bot_poll_all_sources_api_rejects_missing_scope():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.read']

    response = client.post('/admin/bot/api/commands/poll-all')

    assert response.status_code == 403
    payload = response.get_json()
    assert payload['error']['required_scopes'] == ['syndication.write']


def test_admin_bot_poll_all_sources_api_returns_summary(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'syndication.write']

    now = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(admin_bot, '_utcnow', lambda: now)
    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=None,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    repository = InMemorySyndicationSourceRepository(
        [SyndicationSourceState(source_key='youtube', checkpoint='video-123')]
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: repository,
    )
    item = SyndicationItem(
        source_key='youtube',
        external_id='video-200',
        title='Fresh clip',
        canonical_url='https://www.youtube.com/watch?v=video-200',
        published_at=now,
    )
    monkeypatch.setattr(
        admin_bot,
        'build_syndication_adapters',
        lambda config: {
            'youtube': _FakeRetryAdapter(
                SyndicationFetchResult(
                    items=(item,), next_checkpoint='video-200')
            )
        },
    )

    response = client.post('/admin/bot/api/commands/poll-all')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['source_count'] == 1
    assert payload['data']['delivered_items'] == 1
    assert payload['data']['sources'][0]['checkpoint'] == 'video-200'


class _FakeRetryAdapter:
    source_key = 'youtube'

    def __init__(self, result: SyndicationFetchResult):
        self.result = result

    def fetch_since(self, *, checkpoint: str | None = None) -> SyndicationFetchResult:
        return self.result


def test_admin_bot_retry_syndication_api_rejects_missing_scope(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.read']

    response = client.post('/admin/bot/api/syndication/sources/youtube/retry')

    assert response.status_code == 403
    payload = response.get_json()
    assert payload['error']['required_scopes'] == ['syndication.write']


def test_admin_bot_retry_syndication_api_updates_source_state(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'syndication.write']

    now = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(admin_bot, '_utcnow', lambda: now)
    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    repository = InMemorySyndicationSourceRepository(
        [SyndicationSourceState(source_key='youtube', checkpoint='video-123')]
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: repository,
    )
    item = SyndicationItem(
        source_key='youtube',
        external_id='video-200',
        title='Fresh clip',
        canonical_url='https://www.youtube.com/watch?v=video-200',
        published_at=now,
    )
    monkeypatch.setattr(
        admin_bot,
        'build_syndication_adapters',
        lambda config: {
            'youtube': _FakeRetryAdapter(
                SyndicationFetchResult(
                    items=(item,), next_checkpoint='video-200')
            )
        },
    )

    response = client.post('/admin/bot/api/syndication/sources/youtube/retry')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['delivered_items'] == 1
    assert payload['data']['checkpoint'] == 'video-200'
    assert payload['data']['last_poll_result'] == 'succeeded'


def test_admin_bot_reset_syndication_checkpoint_api_clears_checkpoint(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'syndication.write']

    monkeypatch.setattr(
        admin_bot,
        '_load_bot_runtime_settings',
        lambda: BotRuntimeSettings(
            discord_token='token-value',
            guild_id=987654321,
            channel_map={'announcements': 200},
            database_url='postgresql://user:pass@localhost/omo',
            syndication_sources=('youtube',),
            syndication_poll_seconds=300,
            log_level='INFO',
        ),
    )
    repository = InMemorySyndicationSourceRepository(
        [SyndicationSourceState(source_key='youtube', checkpoint='video-123')]
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_syndication_repository',
        lambda database_url: repository,
    )

    response = client.post(
        '/admin/bot/api/syndication/sources/youtube/checkpoint/reset')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['checkpoint'] is None


def test_admin_bot_disable_operator_api_disables_record(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.admin']

    monkeypatch.setattr(
        bot_operator_repo,
        'set_bot_operator_active',
        lambda user_id, is_active: {
            'discord_user_id': user_id,
            'username': 'operator',
            'global_name': 'Operator Name',
            'avatar_url': None,
            'scopes': ['ops.read'],
            'is_active': is_active,
            'last_login_at': None,
        },
    )

    response = client.post('/admin/bot/api/operators/123456/disable')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['discord_user_id'] == '123456'
    assert payload['data']['is_active'] is False


def test_admin_bot_disable_operator_api_emits_audit_entry(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SESSION_ID_KEY] = 'session-1'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.admin']

    monkeypatch.setattr(
        bot_operator_repo,
        'get_bot_operator_by_discord_user_id',
        lambda user_id: {
            'discord_user_id': user_id,
            'username': 'operator',
            'global_name': 'Operator Name',
            'avatar_url': None,
            'scopes': ['ops.read'],
            'is_active': True,
            'last_login_at': None,
        },
    )
    monkeypatch.setattr(
        bot_operator_repo,
        'set_bot_operator_active',
        lambda user_id, is_active: {
            'discord_user_id': user_id,
            'username': 'operator',
            'global_name': 'Operator Name',
            'avatar_url': None,
            'scopes': ['ops.read'],
            'is_active': is_active,
            'last_login_at': None,
        },
    )
    audit_repository = InMemoryBotAuditLogRepository()
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: audit_repository,
    )

    response = client.post('/admin/bot/api/operators/123456/disable')

    assert response.status_code == 200
    assert len(audit_repository.entries) == 1
    entry = audit_repository.entries[0]
    assert entry.action_key == 'operator.disabled'
    assert entry.target_key == '123456'
    assert entry.before_state is not None
    assert entry.before_state['is_active'] is True
    assert entry.after_state is not None
    assert entry.after_state['is_active'] is False


def test_admin_bot_disable_operator_api_rejects_missing_scope(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()
    called = {'value': False}

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.read']

    def fake_set_bot_operator_active(user_id, is_active):
        called['value'] = True
        return None

    monkeypatch.setattr(
        bot_operator_repo,
        'set_bot_operator_active',
        fake_set_bot_operator_active,
    )

    response = client.post('/admin/bot/api/operators/123456/disable')

    assert response.status_code == 403
    payload = response.get_json()
    assert payload['error']['code'] == 'operator_scope_required'
    assert payload['error']['required_scopes'] == ['operators.write']
    assert called['value'] is False


def test_admin_bot_enable_operator_api_enables_record(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.admin']

    monkeypatch.setattr(
        bot_operator_repo,
        'set_bot_operator_active',
        lambda user_id, is_active: {
            'discord_user_id': user_id,
            'username': 'operator',
            'global_name': 'Operator Name',
            'avatar_url': None,
            'scopes': ['ops.read'],
            'is_active': is_active,
            'last_login_at': None,
        },
    )

    response = client.post('/admin/bot/api/operators/123456/enable')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['discord_user_id'] == '123456'
    assert payload['data']['is_active'] is True


def test_admin_bot_update_operator_scopes_api_updates_scopes(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'operators.write']

    monkeypatch.setattr(
        bot_operator_repo,
        'set_bot_operator_scopes',
        lambda user_id, scopes: {
            'discord_user_id': user_id,
            'username': 'operator',
            'global_name': 'Operator Name',
            'avatar_url': None,
            'scopes': scopes,
            'is_active': True,
            'last_login_at': None,
        },
    )

    response = client.post(
        '/admin/bot/api/operators/123456/scopes',
        json={'scopes': ['ops.read', 'queue.write']},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['scopes'] == ['ops.read', 'queue.write']


def test_admin_bot_update_operator_scopes_api_rejects_empty_scopes(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()
    called = {'value': False}

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'operators.write']

    def fake_set_bot_operator_scopes(user_id, scopes):
        called['value'] = True
        return None

    monkeypatch.setattr(
        bot_operator_repo,
        'set_bot_operator_scopes',
        fake_set_bot_operator_scopes,
    )

    response = client.post(
        '/admin/bot/api/operators/123456/scopes',
        json={'scopes': []},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error']['code'] == 'invalid_operator_scopes'
    assert called['value'] is False
