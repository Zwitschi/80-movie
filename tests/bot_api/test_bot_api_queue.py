from bot.omo_bot.config import BotRuntimeSettings
from bot.omo_bot.repositories import InMemoryBotAuditLogRepository, InMemoryQueueRepository
from bot.omo_bot.services import QueueService

import bot_api.admin_bot as admin_bot
from bot_api.app import create_app


def test_bot_api_queues_page_renders_queue_summary(monkeypatch):
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

    response = client.get('/bot/queues')

    assert response.status_code == 200
    assert b'Bot Queues' in response.data
    assert b'Open Mic' in response.data
    assert b'guild-1:open-mic' in response.data


def test_bot_api_advance_queue_api_updates_snapshot_and_emits_audit_entry(monkeypatch):
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

    response = client.post('/bot/api/queues/guild-1:open-mic/advance')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['event']['event_type'] == 'queue_advanced'
    assert payload['data']['summary']['active_entry_id'] is not None
    assert payload['data']['entries'][0]['state'] == 'active'
    assert len(audit_repository.entries) == 1
    assert audit_repository.entries[0].action_key == 'queue.advanced'