import pytest
from control_room.app import create_app as create_control_room_app
from bot.omo_bot.models import MileageTotal, MileageEvent
from bot.omo_bot.repositories import InMemoryMileageRepository


@pytest.fixture
def app():
    app = create_control_room_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_mileage_lifecycle_via_api(client, monkeypatch):
    from bot.omo_bot.config import BotRuntimeSettings
    from control_room import admin_bot

    repo = InMemoryMileageRepository()

    def mock_load_settings():
        return BotRuntimeSettings(
            database_url="postgresql://fake",
            discord_token="fake",
            guild_id=123,
            channel_map={},
            syndication_sources=[],
            syndication_poll_seconds=300,
            role_map={},
        )

    def mock_build_repo(url):
        return repo

    def mock_build_audit_service():
        from bot.omo_bot.services import BotAuditService
        from bot.omo_bot.repositories import InMemoryBotAuditLogRepository
        return BotAuditService(InMemoryBotAuditLogRepository())

    monkeypatch.setattr(
        admin_bot, '_load_bot_runtime_settings', mock_load_settings)
    monkeypatch.setattr(
        admin_bot, 'build_postgres_mileage_repository', mock_build_repo)
    monkeypatch.setattr(admin_bot, '_build_bot_audit_service',
                        mock_build_audit_service)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)

    with client.session_transaction() as sess:
        sess[admin_bot.BOT_OPS_SESSION_KEY] = 'test-user'
        sess[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'mileage.read', 'mileage.write']
        sess[admin_bot.BOT_OPS_LOGIN_AT_KEY] = '2026-05-20T10:00:00Z'
        sess[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = '2026-05-20T10:00:00Z'

    # 1. Adjust Mileage
    response = client.post(
        '/bot/api/mileage/users/user1/adjust',
        json={
            'display_name': 'User One',
            'delta': 50,
            'reason': 'Good contribution'
        }
    )
    if response.status_code != 200:
        print(response.get_json())
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['total']['total_points'] == 50
    assert data['total']['display_name'] == 'User One'

    # 2. Check Event List
    response = client.get('/bot/api/mileage/users/user1')
    assert response.status_code == 200
    data = response.get_json()['data']
    assert len(data['events']) == 1
    event_id = data['events'][0]['event_id']

    # 3. Reverse Event
    response = client.post(
        f'/bot/api/mileage/events/{event_id}/reverse',
        json={'reason': 'Typo in adjustment'}
    )
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['total']['total_points'] == 0

