import pytest
from control_room.app import create_app as create_control_room_app
from bot.omo_bot.models import QueueSnapshot, QueueEvent
from bot.omo_bot.repositories import InMemoryQueueRepository


@pytest.fixture
def app():
    app = create_control_room_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_queue_lifecycle_via_api(client, monkeypatch):
    # Mock settings and repository to use in-memory for testing
    from bot.omo_bot.config import BotRuntimeSettings
    from control_room import admin_bot

    repo = InMemoryQueueRepository()

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
        admin_bot, 'build_postgres_queue_repository', mock_build_repo)
    monkeypatch.setattr(
        admin_bot, '_build_bot_audit_service', mock_build_audit_service)
    monkeypatch.setattr(admin_bot, '_operator_can', lambda scope: True)

    with client.session_transaction() as sess:
        sess[admin_bot.BOT_OPS_SESSION_KEY] = 'test-user'
        sess[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = [
            'queue.read', 'queue.write']
        sess[admin_bot.BOT_OPS_LOGIN_AT_KEY] = '2026-05-20T10:00:00Z'
        sess[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = '2026-05-20T10:00:00Z'

    # 1. Join Queue (via ensure_queue which is called by other actions, or we can use a direct join if we add it)
    # The control room doesn't have a direct "join" API for operators to add users yet,
    # but it has "advance", "pause", "resume", "clear".

    # Initialize a queue
    repo.save_queue(
        summary=admin_bot.QueueSummary(
            queue_id="test-queue",
            guild_id=123,
            label="Test Queue",
            is_paused=False,
            paused_reason="",
            active_entry_id=None,
            waiting_count=0,
            total_entries=0,
            updated_at=None
        ),
        entries=()
    )

    # 2. Pause Queue
    response = client.post(
        '/admin/bot/api/queues/test-queue/pause', json={'reason': 'Taking a break'})
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['summary']['is_paused'] is True
    assert data['summary']['paused_reason'] == 'Taking a break'

    # 3. Resume Queue
    response = client.post('/admin/bot/api/queues/test-queue/resume')
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['summary']['is_paused'] is False

    # 4. Clear Queue
    response = client.post(
        '/admin/bot/api/queues/test-queue/clear', json={'confirm': 'clear'})
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['summary']['total_entries'] == 0
