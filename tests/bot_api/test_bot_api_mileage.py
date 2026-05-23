from bot.omo_bot.config import BotRuntimeSettings
from bot.omo_bot.repositories import InMemoryBotAuditLogRepository, InMemoryMileageRepository
from bot.omo_bot.services import MileageService

import bot_api.admin_bot as admin_bot
from bot_api.app import create_app


def test_bot_api_mileage_page_renders_user_summary_and_tiers(monkeypatch):
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
    mileage_repository = InMemoryMileageRepository()
    mileage_service = MileageService(mileage_repository)
    mileage_service.upsert_tier(
        guild_id=987654321, name='Bronze', points_required=10, sort_order=1)
    mileage_service.adjust_user_mileage(
        guild_id=987654321,
        discord_user_id='u1',
        display_name='Alpha',
        points_delta=12,
        reason='Hosted event',
    )
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_mileage_repository',
        lambda database_url: mileage_repository,
    )

    response = client.get('/bot/mileage')

    assert response.status_code == 200
    assert b'Mileage / XP' in response.data
    assert b'Alpha' in response.data
    assert b'Bronze' in response.data


def test_bot_api_adjust_mileage_user_api_updates_total_and_emits_audit_entry(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SESSION_ID_KEY] = 'session-1'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['mileage.write']

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
    mileage_repository = InMemoryMileageRepository()
    mileage_service = MileageService(mileage_repository)
    mileage_service.upsert_tier(
        guild_id=987654321, name='Bronze', points_required=10, sort_order=1)
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_mileage_repository',
        lambda database_url: mileage_repository,
    )
    audit_repository = InMemoryBotAuditLogRepository()
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: audit_repository,
    )

    response = client.post(
        '/bot/api/mileage/users/u1/adjust',
        json={
            'display_name': 'Alpha',
            'delta': 12,
            'reason': 'Hosted event',
            'correlation_id': 'adjust-1',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['event']['event_type'] == 'manual_adjustment'
    assert payload['data']['total']['total_points'] == 12
    assert len(audit_repository.entries) == 1
    assert audit_repository.entries[0].action_key == 'mileage.adjusted'


def test_bot_api_reverse_mileage_event_api_appends_reversal_and_audit(monkeypatch):
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as flask_session:
        flask_session[admin_bot.BOT_OPS_SESSION_KEY] = '123456'
        flask_session[admin_bot.BOT_OPS_SESSION_ID_KEY] = 'session-1'
        flask_session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = ['mileage.write']

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
    mileage_repository = InMemoryMileageRepository()
    mileage_service = MileageService(mileage_repository)
    event_detail, original_event = mileage_service.adjust_user_mileage(
        guild_id=987654321,
        discord_user_id='u1',
        display_name='Alpha',
        points_delta=9,
        reason='Volunteer shift',
        actor_user_id='operator-1',
    )
    assert event_detail.total.total_points == 9
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_mileage_repository',
        lambda database_url: mileage_repository,
    )
    audit_repository = InMemoryBotAuditLogRepository()
    monkeypatch.setattr(
        admin_bot,
        'build_postgres_bot_audit_log_repository',
        lambda database_url: audit_repository,
    )

    response = client.post(
        f'/bot/api/mileage/events/{original_event.event_id}/reverse',
        json={'reason': 'Duplicate credit'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['meta']['event']['event_type'] == 'manual_reversal'
    assert payload['data']['total']['total_points'] == 0
    assert len(audit_repository.entries) == 1
    assert audit_repository.entries[0].action_key == 'mileage.reversed'
