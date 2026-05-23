from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import cast
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import bot_api.admin_bot as admin_bot
import bot_api.bot_operator_service as bot_operator_service
from bot_api.app import create_app


def test_bot_api_page_redirects_without_operator_session_when_not_testing():
    app = create_app()
    client = app.test_client()

    response = client.get('/bot')

    assert response.status_code == 302
    assert '/bot/login' in response.headers['Location']


def test_bot_api_api_requires_operator_session_when_not_testing():
    app = create_app()
    client = app.test_client()

    response = client.get('/bot/api/health')

    assert response.status_code == 401
    payload = response.get_json()
    assert payload['error']['code'] == 'operator_auth_required'


def test_bot_api_oauth_start_redirects_and_sets_state():
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/oauth/discord/callback',
    )
    client = app.test_client()

    response = client.get('/bot/oauth/start?next=/bot/health')

    assert response.status_code == 302
    location = response.headers['Location']
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.netloc == 'discord.com'
    assert query['client_id'] == ['client-id']
    assert query['redirect_uri'] == [
        'https://example.com/oauth/discord/callback']
    assert query['scope'] == ['identify']

    with client.session_transaction() as flask_session:
        assert flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY]
        assert flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] == '/bot/health'


def test_bot_api_oauth_start_uses_env_driven_config(monkeypatch):
    monkeypatch.setenv('OMO_DISCORD_CLIENT_ID', 'env-client-id')
    monkeypatch.setenv('OMO_DISCORD_CLIENT_SECRET', 'env-client-secret')
    monkeypatch.setenv(
        'OMO_DISCORD_REDIRECT_URI',
        'https://example.com/oauth/discord/callback',
    )

    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/bot/oauth/start?next=/bot/health')

    assert response.status_code == 302
    location = response.headers['Location']
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert query['client_id'] == ['env-client-id']
    assert query['redirect_uri'] == [
        'https://example.com/oauth/discord/callback']


def test_bot_api_oauth_callback_rejects_state_mismatch():
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/oauth/discord/callback',
    )
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'

    response = client.get(
        '/bot/oauth/callback?state=wrong-state&code=test-code')

    assert response.status_code == 400
    assert b'OAuth state did not match' in response.data


def test_discord_oauth_callback_alias_is_reachable(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://api.openmicodyssey.com/oauth/discord/callback',
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
    monkeypatch.setattr(bot_operator_service,
                        'persist_operator_login', lambda **kwargs: None)

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'
        flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] = '/bot/health'

    response = client.get(
        '/oauth/discord/callback?state=expected-state&code=test-code')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/bot/health')


def test_exchange_code_for_discord_identity_surfaces_http_error_as_operator_auth_error(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://api.openmicodyssey.com/oauth/discord/callback',
    )
    requests: list[object] = []

    def fake_urlopen(request, timeout=10):
        requests.append(request)
        raise HTTPError(
            request.full_url,
            403,
            'Forbidden',
            hdrs=None,
            fp=BytesIO(b'{"error":"access_denied"}'),
        )

    monkeypatch.setattr(admin_bot, 'urlopen', fake_urlopen)

    with app.app_context():
        try:
            admin_bot.exchange_code_for_discord_identity('test-code')
            assert False, 'expected OperatorAuthError'
        except admin_bot.OperatorAuthError as exc:
            message = str(exc)

    assert 'HTTP 403' in message
    assert 'access_denied' in message
    assert requests
    assert requests[0].headers['User-agent'] == admin_bot.DISCORD_HTTP_USER_AGENT


def test_bot_api_oauth_callback_sets_operator_session_for_allowed_user(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/oauth/discord/callback',
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
    monkeypatch.setattr(bot_operator_service,
                        'persist_operator_login', lambda **kwargs: None)

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'
        flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] = '/bot/health'

    response = client.get(
        '/bot/oauth/callback?state=expected-state&code=test-code')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/bot/health')
    with client.session_transaction() as flask_session:
        assert flask_session[admin_bot.BOT_OPS_SESSION_KEY] == '123456'
        assert flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] == [
            'ops.read', 'queue.write']
        assert admin_bot.BOT_OPS_OAUTH_STATE_KEY not in flask_session


def test_bot_api_oauth_callback_rejects_disallowed_operator(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/oauth/discord/callback',
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
        '/bot/oauth/callback?state=expected-state&code=test-code')

    assert response.status_code == 403
    assert b'not on the control-room allowlist' in response.data


def test_bot_api_oauth_callback_accepts_db_backed_operator_record(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/oauth/discord/callback',
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
    monkeypatch.setattr(bot_operator_service,
                        'persist_operator_login', lambda **kwargs: None)

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'
        flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] = '/bot/health'

    response = client.get(
        '/bot/oauth/callback?state=expected-state&code=test-code')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/bot/health')
    with client.session_transaction() as flask_session:
        assert flask_session[admin_bot.BOT_OPS_SESSION_KEY] == 'db-user'
        assert flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] == [
            'ops.read', 'syndication.write']


def test_bot_api_oauth_callback_persists_operator_profile_metadata(monkeypatch):
    app = create_app()
    app.config.update(
        TESTING=True,
        BOT_OPS_DISCORD_CLIENT_ID='client-id',
        BOT_OPS_DISCORD_CLIENT_SECRET='client-secret',
        BOT_OPS_DISCORD_REDIRECT_URI='https://example.com/oauth/discord/callback',
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
    monkeypatch.setattr(bot_operator_service, 'persist_operator_login',
                        lambda **kwargs: persisted.update(kwargs))

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = 'expected-state'
        flask_session[admin_bot.BOT_OPS_NEXT_URL_KEY] = '/bot/health'

    response = client.get(
        '/bot/oauth/callback?state=expected-state&code=test-code')

    assert response.status_code == 302
    operator_identity = cast(dict[str, object], persisted['operator_identity'])
    assert operator_identity['user_id'] == '123456'
    assert operator_identity['username'] == 'operator'
    assert operator_identity['global_name'] == 'Operator Name'
    assert operator_identity['avatar_url'] == 'https://cdn.example/avatar.png'
    assert persisted['scopes'] == ['ops.read', 'queue.write']
    assert persisted['last_login_at']


def test_bot_api_logout_clears_only_operator_session_keys():
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

    response = client.post('/bot/logout')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/bot/login')
    with client.session_transaction() as flask_session:
        assert admin_bot.BOT_OPS_SESSION_KEY not in flask_session
        assert admin_bot.BOT_OPS_SESSION_ID_KEY not in flask_session
        assert flask_session['editorial_marker'] == 'keep-me'


def test_bot_api_page_redirects_when_operator_session_is_idle_timed_out():
    app = create_app()
    app.config['BOT_OPS_SESSION_IDLE_MINUTES'] = 5
    client = app.test_client()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = stale

    response = client.get('/bot')

    assert response.status_code == 302
    assert 'error=session-expired' in response.headers['Location']
    with client.session_transaction() as flask_session:
        assert admin_bot.BOT_OPS_SESSION_KEY not in flask_session


def test_bot_api_api_returns_session_expired_for_idle_timeout():
    app = create_app()
    app.config['BOT_OPS_SESSION_IDLE_MINUTES'] = 5
    client = app.test_client()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = stale

    response = client.get('/bot/api/health')

    assert response.status_code == 401
    payload = response.get_json()
    assert payload['error']['code'] == 'operator_session_expired'


def test_bot_api_authenticated_request_refreshes_last_seen():
    app = create_app()
    app.config['BOT_OPS_SESSION_IDLE_MINUTES'] = 60
    client = app.test_client()
    older = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = older

    response = client.get('/bot/health')

    assert response.status_code == 200
    with client.session_transaction() as flask_session:
        refreshed = flask_session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY]
        assert refreshed != older
