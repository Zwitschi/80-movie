from datetime import datetime, timedelta, timezone
from typing import cast
from urllib.parse import parse_qs, urlparse

from website.app import create_app
from website.movie_site import admin_bot
from website.movie_site import bot_operator_repo
from website.movie_site import bot_operator_service


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
