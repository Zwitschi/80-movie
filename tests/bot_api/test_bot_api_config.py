from bot.config import BotRuntimeSettings
from bot.models import SyndicationSourceState
from bot.repositories import InMemoryBotConfigRepository, InMemorySyndicationSourceRepository

import bot_api.admin_bot as admin_bot
from bot_api.app import create_app


class _FailingAuditRepository:
    def append(self, entry):
        raise RuntimeError('audit unavailable')


def test_bot_api_config_page_renders_sources_and_channel_bindings(monkeypatch):
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

    response = client.get('/bot/config')

    assert response.status_code == 200
    assert b'Runtime Configuration' in response.data
    assert b'Syndication Sources' in response.data
    assert b'Channel Bindings' in response.data
    assert b'Role Bindings' in response.data
    assert b'announcements' in response.data
    assert b'moderator' in response.data


def test_bot_api_config_api_returns_repository_managed_bindings(monkeypatch):
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

    response = client.get('/bot/api/config')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['guild_config']['guild_id'] == 222
    assert payload['data']['channel_bindings'][0]['binding_key'] == 'queue'
    assert payload['data']['channel_bindings'][0]['channel_id'] == 300
    assert payload['data']['role_bindings'][0]['binding_key'] == 'moderator'
    assert payload['data']['role_bindings'][0]['role_id'] == 400


def test_bot_api_upsert_channel_binding_api_updates_repository(monkeypatch):
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
        '/bot/api/config/channels',
        json={'binding_key': 'announcements', 'channel_id': 200},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['binding_key'] == 'announcements'
    assert payload['data']['channel_id'] == 200
    assert repository.list_channel_bindings(222) == [
        {'guild_id': 222, 'binding_key': 'announcements', 'channel_id': 200}
    ]


def test_bot_api_upsert_channel_binding_api_succeeds_when_audit_is_degraded(monkeypatch):
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
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: _FailingAuditRepository(),
    )

    response = client.post(
        '/bot/api/config/channels',
        json={'binding_key': 'announcements', 'channel_id': 200},
    )

    assert response.status_code == 200
    assert response.headers[admin_bot.BOT_AUDIT_STATUS_HEADER] == 'degraded'
    assert repository.list_channel_bindings(222) == [
        {'guild_id': 222, 'binding_key': 'announcements', 'channel_id': 200}
    ]
