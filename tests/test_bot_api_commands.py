from datetime import datetime, timezone

from bot.omo_bot.config import BotRuntimeSettings
from bot.omo_bot.models import SyndicationFetchResult, SyndicationItem, SyndicationSourceState
from bot.omo_bot.repositories import InMemorySyndicationSourceRepository

import bot_api.admin_bot as admin_bot
from bot_api.app import create_app


class _FakeRetryAdapter:
    source_key = 'youtube'

    def __init__(self, result: SyndicationFetchResult):
        self.result = result

    def fetch_since(self, *, checkpoint: str | None = None) -> SyndicationFetchResult:
        return self.result


def test_bot_api_commands_page_renders_poll_all_command(monkeypatch):
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

    response = client.get('/bot/commands')

    assert response.status_code == 200
    assert b'Command Actions' in response.data
    assert b'Poll all sources now' in response.data


def test_bot_api_poll_all_sources_api_rejects_missing_scope():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['ops.read']

    response = client.post('/bot/api/commands/poll-all')

    assert response.status_code == 403
    payload = response.get_json()
    assert payload['error']['required_scopes'] == ['syndication.write']


def test_bot_api_poll_all_sources_api_returns_summary(monkeypatch):
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

    response = client.post('/bot/api/commands/poll-all')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['source_count'] == 1
    assert payload['data']['delivered_items'] == 1
    assert payload['data']['sources'][0]['checkpoint'] == 'video-200'
