from bot.omo_bot.repositories import InMemoryBotAuditLogRepository

import bot_api.admin_bot as admin_bot
import bot_api.bot_operator_repo as bot_operator_repo
from bot_api.app import create_app


class _FailingAuditRepository:
    def append(self, entry):
        raise RuntimeError('audit unavailable')


def test_bot_api_operators_page_renders_list(monkeypatch):
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

    response = client.get('/bot/operators')

    assert response.status_code == 200
    assert b'Bot Operators' in response.data
    assert b'Operator Name' in response.data
    assert b'queue.write' in response.data


def test_bot_api_operators_api_returns_records(monkeypatch):
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

    response = client.get('/bot/api/operators')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data'][0]['discord_user_id'] == '123456'


def test_bot_api_disable_operator_api_disables_record(monkeypatch):
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

    response = client.post('/bot/api/operators/123456/disable')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['discord_user_id'] == '123456'
    assert payload['data']['is_active'] is False


def test_bot_api_disable_operator_api_emits_audit_entry(monkeypatch):
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

    response = client.post('/bot/api/operators/123456/disable')

    assert response.status_code == 200
    assert len(audit_repository.entries) == 1
    entry = audit_repository.entries[0]
    assert entry.action_key == 'operator.disabled'
    assert entry.target_key == '123456'
    assert entry.before_state is not None
    assert entry.before_state['is_active'] is True
    assert entry.after_state is not None
    assert entry.after_state['is_active'] is False


def test_bot_api_disable_operator_api_succeeds_when_audit_is_degraded(monkeypatch):
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
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: _FailingAuditRepository(),
    )

    response = client.post('/bot/api/operators/123456/disable')

    assert response.status_code == 200
    assert response.headers[admin_bot.BOT_AUDIT_STATUS_HEADER] == 'degraded'
    payload = response.get_json()
    assert payload['data']['discord_user_id'] == '123456'
    assert payload['data']['is_active'] is False


def test_bot_api_disable_operator_api_rejects_missing_scope(monkeypatch):
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

    response = client.post('/bot/api/operators/123456/disable')

    assert response.status_code == 403
    payload = response.get_json()
    assert payload['error']['code'] == 'operator_scope_required'
    assert payload['error']['required_scopes'] == ['operators.write']
    assert called['value'] is False


def test_bot_api_enable_operator_api_enables_record(monkeypatch):
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

    response = client.post('/bot/api/operators/123456/enable')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['discord_user_id'] == '123456'
    assert payload['data']['is_active'] is True


def test_bot_api_update_operator_scopes_api_updates_scopes(monkeypatch):
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
        '/bot/api/operators/123456/scopes',
        json={'scopes': ['ops.read', 'queue.write']},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['scopes'] == ['ops.read', 'queue.write']


def test_bot_api_update_operator_scopes_api_rejects_empty_scopes(monkeypatch):
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
        '/bot/api/operators/123456/scopes',
        json={'scopes': []},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['error']['code'] == 'invalid_operator_scopes'
    assert called['value'] is False
