from datetime import datetime, timezone

from bot.config import BotRuntimeSettings
from bot.models import SyndicationSourceState
from bot.repositories import InMemorySyndicationSourceRepository

import bot_api.admin_bot as admin_bot
from bot_api.app import create_app


def test_bot_api_overview_renders_in_testing_mode():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/bot')

    assert response.status_code == 200
    assert b'Bot Overview' in response.data
    assert b'Component Snapshot' in response.data


def test_bot_api_root_redirects_to_operator_dashboard():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/bot')


def test_bot_api_health_api_returns_snapshot_in_testing_mode():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/bot/api/health')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data']['status'] in {'ok', 'degraded'}
    assert 'components' in payload['data']
    assert 'database' in payload['data']['components']
    assert payload['data']['links']['health'].endswith('/bot/api/health')


def test_bot_api_health_page_renders_syndication_summary(monkeypatch):
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

    response = client.get('/bot/health')

    assert response.status_code == 200
    assert b'Syndication Status' in response.data
    assert b'Attention sources' in response.data


def test_bot_api_services_api_returns_component_details():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    response = client.get('/bot/api/health/services')

    assert response.status_code == 200
    payload = response.get_json()
    assert 'website_app' in payload['data']
    assert 'jobs' in payload['data']
