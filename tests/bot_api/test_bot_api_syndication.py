from datetime import datetime, timezone

from bot.config import BotRuntimeSettings
from bot.models import SyndicationFetchResult, SyndicationItem, SyndicationSourceState
from bot.repositories import InMemoryBotAuditLogRepository, InMemorySyndicationSourceRepository

import bot_api.admin_bot as admin_bot
from bot_api.app import create_app


class _FailingAuditRepository:
    def append(self, entry):
        raise RuntimeError('audit unavailable')


class _FakeRetryAdapter:
    source_key = 'youtube'

    def __init__(self, result: SyndicationFetchResult):
        self.result = result

    def fetch_since(self, *, checkpoint: str | None = None) -> SyndicationFetchResult:
        return self.result


def test_bot_api_syndication_page_renders_configured_sources(monkeypatch):
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

    response = client.get('/bot/syndication')

    assert response.status_code == 200
    assert b'Configured Sources' in response.data
    assert b'Last poll result' in response.data
    assert b'youtube' in response.data
    assert b'video-123' in response.data
    assert b'announcements' in response.data


def test_bot_api_syndication_page_renders_retry_controls_for_writer(monkeypatch):
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

    response = client.get('/bot/syndication')

    assert response.status_code == 200
    assert b'Retry poll' in response.data
    assert b'Reset checkpoint' in response.data


def test_bot_api_syndication_sources_api_returns_snapshot(monkeypatch):
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

    response = client.get('/bot/api/syndication/sources')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['status'] == 'ok'
    assert payload['data'][0]['source_key'] == 'youtube'
    assert payload['data'][0]['checkpoint'] == 'video-123'


def test_bot_api_syndication_channels_api_returns_bindings(monkeypatch):
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

    response = client.get('/bot/api/syndication/channels')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['status'] == 'ok'
    assert payload['data'] == [
        {'binding_key': 'announcements', 'channel_id': 200},
        {'binding_key': 'queue', 'channel_id': 100},
    ]


def test_bot_api_disable_syndication_source_api_updates_enabled_state(monkeypatch):
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

    response = client.post('/bot/api/config/sources/youtube/disable')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['enabled'] is False


def test_bot_api_disable_syndication_source_api_emits_audit_entry(monkeypatch):
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

    response = client.post('/bot/api/config/sources/youtube/disable')

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


def test_bot_api_disable_syndication_source_api_succeeds_when_audit_is_degraded(monkeypatch):
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
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: _FailingAuditRepository(),
    )

    response = client.post('/bot/api/config/sources/youtube/disable')

    assert response.status_code == 200
    assert response.headers[admin_bot.BOT_AUDIT_STATUS_HEADER] == 'degraded'
    assert repository.get_by_source_key('youtube') is not None
    assert repository.get_by_source_key('youtube').enabled is False


def test_bot_api_retry_syndication_api_rejects_missing_scope(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.read']

    response = client.post('/bot/api/syndication/sources/youtube/retry')

    assert response.status_code == 403
    payload = response.get_json()
    assert payload['error']['required_scopes'] == ['syndication.write']


def test_bot_api_retry_syndication_api_updates_source_state(monkeypatch):
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

    response = client.post('/bot/api/syndication/sources/youtube/retry')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['delivered_items'] == 1
    assert payload['data']['checkpoint'] == 'video-200'
    assert payload['data']['last_poll_result'] == 'succeeded'


def test_bot_api_reset_syndication_checkpoint_api_clears_checkpoint(monkeypatch):
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
        '/bot/api/syndication/sources/youtube/checkpoint/reset')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['checkpoint'] is None
