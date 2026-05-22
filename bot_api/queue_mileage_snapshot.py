from __future__ import annotations

from typing import cast

from flask import url_for


def _build_queue_service_from_settings(settings):
    from . import admin_bot

    if not settings.database_url:
        raise admin_bot.ConfigError(
            'Queue operations require a configured database-backed repository.'
        )
    return admin_bot.QueueService(
        admin_bot.build_postgres_queue_repository(settings.database_url)
    )


def _serialize_queue_summary(summary, *, can_write: bool) -> dict[str, object]:
    return {
        'queue_id': summary.queue_id,
        'guild_id': summary.guild_id,
        'label': summary.label,
        'is_paused': summary.is_paused,
        'paused_reason': summary.paused_reason,
        'active_entry_id': summary.active_entry_id,
        'waiting_count': summary.waiting_count,
        'total_entries': summary.total_entries,
        'updated_at': summary.updated_at.isoformat() if summary.updated_at else None,
        'detail_api': url_for('bot.queue_detail_api', queue_id=summary.queue_id),
        'detail_page': url_for('bot.queue_detail_page', queue_id=summary.queue_id),
        'events_api': url_for('bot.queue_events_api', queue_id=summary.queue_id),
        'advance_api': url_for('bot.advance_queue_api', queue_id=summary.queue_id),
        'advance_page': url_for('bot.advance_queue_page_action', queue_id=summary.queue_id),
        'pause_api': url_for('bot.pause_queue_api', queue_id=summary.queue_id),
        'pause_page': url_for('bot.pause_queue_page_action', queue_id=summary.queue_id),
        'resume_api': url_for('bot.resume_queue_api', queue_id=summary.queue_id),
        'resume_page': url_for('bot.resume_queue_page_action', queue_id=summary.queue_id),
        'clear_api': url_for('bot.clear_queue_api', queue_id=summary.queue_id),
        'clear_page': url_for('bot.clear_queue_page_action', queue_id=summary.queue_id),
        'editable': can_write,
    }


def _serialize_queue_entry(entry, *, can_write: bool) -> dict[str, object]:
    return {
        'entry_id': entry.entry_id,
        'queue_id': entry.queue_id,
        'discord_user_id': entry.discord_user_id,
        'display_name': entry.display_name,
        'state': entry.state,
        'position': entry.position,
        'note': entry.note,
        'joined_at': entry.joined_at.isoformat(),
        'started_at': entry.started_at.isoformat() if entry.started_at else None,
        'remove_api': url_for('bot.remove_queue_entry_api', queue_id=entry.queue_id, entry_id=entry.entry_id),
        'remove_page': url_for('bot.remove_queue_entry_page_action', queue_id=entry.queue_id, entry_id=entry.entry_id),
        'move_api': url_for('bot.move_queue_entry_api', queue_id=entry.queue_id, entry_id=entry.entry_id),
        'move_page': url_for('bot.move_queue_entry_page_action', queue_id=entry.queue_id, entry_id=entry.entry_id),
        'editable': can_write,
    }


def _serialize_queue_event(event) -> dict[str, object]:
    from . import admin_bot

    return {
        'event_id': event.event_id,
        'queue_id': event.queue_id,
        'event_type': event.event_type,
        'actor_user_id': event.actor_user_id,
        'entry_id': event.entry_id,
        'payload': cast(dict[str, object], admin_bot._serialize_audit_value(event.payload)),
        'created_at': event.created_at.isoformat(),
    }


def _serialize_queue_snapshot(snapshot, *, can_write: bool) -> dict[str, object]:
    from . import admin_bot

    return {
        'summary': admin_bot._serialize_queue_summary(snapshot.summary, can_write=can_write),
        'entries': [
            admin_bot._serialize_queue_entry(entry, can_write=can_write)
            for entry in snapshot.entries
        ],
        'last_event': admin_bot._serialize_queue_event(snapshot.last_event) if snapshot.last_event else None,
    }


def _serialize_mileage_total(total, *, can_write: bool) -> dict[str, object]:
    return {
        'guild_id': total.guild_id,
        'discord_user_id': total.discord_user_id,
        'display_name': total.display_name,
        'total_points': total.total_points,
        'current_tier_id': total.current_tier_id,
        'current_tier_name': total.current_tier_name,
        'last_event_id': total.last_event_id,
        'last_event_at': total.last_event_at.isoformat() if total.last_event_at else None,
        'updated_at': total.updated_at.isoformat() if total.updated_at else None,
        'detail_api': url_for('bot.mileage_user_detail_api', user_id=total.discord_user_id),
        'detail_page': url_for('bot.mileage_detail_page', user_id=total.discord_user_id),
        'adjust_api': url_for('bot.adjust_mileage_user_api', user_id=total.discord_user_id),
        'adjust_page': url_for('bot.adjust_mileage_user_page_action', user_id=total.discord_user_id),
        'editable': can_write,
    }


def _serialize_mileage_event(event, *, can_write: bool) -> dict[str, object]:
    from . import admin_bot

    return {
        'event_id': event.event_id,
        'guild_id': event.guild_id,
        'discord_user_id': event.discord_user_id,
        'display_name': event.display_name,
        'event_type': event.event_type,
        'points_delta': event.points_delta,
        'reason': event.reason,
        'actor_user_id': event.actor_user_id,
        'correlation_id': event.correlation_id,
        'reversed_event_id': event.reversed_event_id,
        'metadata': cast(dict[str, object], admin_bot._serialize_audit_value(event.metadata)),
        'created_at': event.created_at.isoformat(),
        'reverse_api': url_for('bot.reverse_mileage_event_api', event_id=event.event_id),
        'reverse_page': url_for('bot.reverse_mileage_event_page_action', event_id=event.event_id),
        'reversible': bool(can_write and event.reversed_event_id is None and event.event_type != 'manual_reversal'),
    }


def _serialize_mileage_tier_stat(tier_stat) -> dict[str, object]:
    return {
        'tier_id': tier_stat.tier.tier_id,
        'guild_id': tier_stat.tier.guild_id,
        'name': tier_stat.tier.name,
        'points_required': tier_stat.tier.points_required,
        'role_id': tier_stat.tier.role_id,
        'sort_order': tier_stat.tier.sort_order,
        'updated_at': tier_stat.tier.updated_at.isoformat() if tier_stat.tier.updated_at else None,
        'user_count': tier_stat.user_count,
    }


def _serialize_mileage_user_detail(detail, *, can_write: bool) -> dict[str, object]:
    from . import admin_bot

    return {
        'total': admin_bot._serialize_mileage_total(detail.total, can_write=can_write),
        'current_tier': admin_bot._serialize_mileage_tier_stat(
            admin_bot.MileageTierStat(detail.current_tier, 0)
        ) if detail.current_tier else None,
        'events': [
            admin_bot._serialize_mileage_event(event, can_write=can_write)
            for event in detail.events
        ],
    }


def _build_mileage_service_from_settings(settings):
    from . import admin_bot

    if not settings.database_url:
        raise admin_bot.ConfigError(
            'Mileage operations require a configured database-backed repository.'
        )
    return admin_bot.MileageService(
        admin_bot.build_postgres_mileage_repository(settings.database_url)
    )


def build_mileage_index_snapshot(*, search: str = '', tier_id: str | None = None) -> dict[str, object]:
    from . import admin_bot

    generated_at = admin_bot._utcnow().isoformat()
    can_write = admin_bot._operator_can('mileage.write')
    try:
        settings = admin_bot._load_bot_runtime_settings()
        guild_id = admin_bot._mileage_active_guild_id(settings)
        service = admin_bot._build_mileage_service_from_settings(settings)
        tier_stats = service.list_tier_stats(guild_id)
        user_totals = service.list_user_summaries(
            guild_id, search=search, tier_id=tier_id)
        return {
            'status': 'ok',
            'generated_at': generated_at,
            'guild_id': guild_id,
            'search': search,
            'selected_tier_id': tier_id,
            'tiers': [admin_bot._serialize_mileage_tier_stat(tier_stat) for tier_stat in tier_stats],
            'users': [admin_bot._serialize_mileage_total(total, can_write=can_write) for total in user_totals],
            'permissions': {'operator_can_write': can_write},
            'repository_error': None,
        }
    except admin_bot.ConfigError as exc:
        return {
            'status': 'missing_config',
            'generated_at': generated_at,
            'guild_id': None,
            'search': search,
            'selected_tier_id': tier_id,
            'tiers': [],
            'users': [],
            'permissions': {'operator_can_write': can_write},
            'repository_error': str(exc),
        }
    except Exception as exc:
        return {
            'status': 'error',
            'generated_at': generated_at,
            'guild_id': None,
            'search': search,
            'selected_tier_id': tier_id,
            'tiers': [],
            'users': [],
            'permissions': {'operator_can_write': can_write},
            'repository_error': str(exc),
        }


def build_mileage_detail_snapshot(user_id: str) -> dict[str, object]:
    from . import admin_bot

    settings = admin_bot._load_bot_runtime_settings()
    guild_id = admin_bot._mileage_active_guild_id(settings)
    service = admin_bot._build_mileage_service_from_settings(settings)
    detail = service.get_user_detail(guild_id, user_id, limit=50)
    can_write = admin_bot._operator_can('mileage.write')
    return {
        'status': 'ok',
        'generated_at': admin_bot._utcnow().isoformat(),
        'guild_id': guild_id,
        'user': admin_bot._serialize_mileage_user_detail(detail, can_write=can_write),
        'permissions': {'operator_can_write': can_write},
    }


def _mileage_user_before_state(service, guild_id: int, user_id: str) -> dict[str, object] | None:
    from . import admin_bot

    try:
        detail = service.get_user_detail(guild_id, user_id, limit=50)
    except admin_bot.MileageNotFoundError:
        return None
    return admin_bot._serialize_mileage_user_detail(
        detail,
        can_write=admin_bot._operator_can('mileage.write'),
    )


def build_queue_index_snapshot() -> dict[str, object]:
    from . import admin_bot

    generated_at = admin_bot._utcnow().isoformat()
    can_write = admin_bot._operator_can('queue.write')
    try:
        settings = admin_bot._load_bot_runtime_settings()
    except admin_bot.ConfigError as exc:
        return {
            'status': 'missing_config',
            'generated_at': generated_at,
            'queues': [],
            'permissions': {'operator_can_write': can_write},
            'repository_error': str(exc),
            'create_api': url_for('bot.create_queue_api'),
            'create_page': url_for('bot.create_queue_page_action'),
        }

    if not settings.database_url:
        return {
            'status': 'missing_config',
            'generated_at': generated_at,
            'queues': [],
            'permissions': {'operator_can_write': can_write},
            'repository_error': 'Queue operations require a configured database-backed repository.',
            'create_api': url_for('bot.create_queue_api'),
            'create_page': url_for('bot.create_queue_page_action'),
        }

    try:
        summaries = admin_bot._build_queue_service_from_settings(
            settings).list_queues()
        return {
            'status': 'ok',
            'generated_at': generated_at,
            'queues': [admin_bot._serialize_queue_summary(summary, can_write=can_write) for summary in summaries],
            'permissions': {'operator_can_write': can_write},
            'repository_error': None,
            'create_api': url_for('bot.create_queue_api'),
            'create_page': url_for('bot.create_queue_page_action'),
        }
    except Exception as exc:
        return {
            'status': 'error',
            'generated_at': generated_at,
            'queues': [],
            'permissions': {'operator_can_write': can_write},
            'repository_error': str(exc),
            'create_api': url_for('bot.create_queue_api'),
            'create_page': url_for('bot.create_queue_page_action'),
        }


def build_queue_detail_snapshot(queue_id: str) -> dict[str, object]:
    from . import admin_bot

    settings = admin_bot._load_bot_runtime_settings()
    queue_service = admin_bot._build_queue_service_from_settings(settings)
    queue_snapshot = queue_service.get_queue(queue_id)
    queue_events = queue_service.list_events(queue_id, limit=20)
    can_write = admin_bot._operator_can('queue.write')
    return {
        'status': 'ok',
        'generated_at': admin_bot._utcnow().isoformat(),
        'queue': admin_bot._serialize_queue_snapshot(queue_snapshot, can_write=can_write),
        'events': [admin_bot._serialize_queue_event(event) for event in queue_events],
        'permissions': {'operator_can_write': can_write},
    }


def _queue_before_state(queue_service, queue_id: str) -> dict[str, object] | None:
    from . import admin_bot

    try:
        snapshot = queue_service.get_queue(queue_id)
    except admin_bot.QueueNotFoundError:
        return None
    return admin_bot._serialize_queue_snapshot(
        snapshot,
        can_write=admin_bot._operator_can('queue.write'),
    )
