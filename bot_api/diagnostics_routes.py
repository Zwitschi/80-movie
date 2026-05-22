from __future__ import annotations

from flask import jsonify


def diagnostics_api():
    from . import admin_bot

    if not admin_bot._operator_can('queue.read', 'onboarding.read', 'mileage.read'):
        return admin_bot._operator_scope_denied_response('queue.read')
    result: dict[str, object] = {}
    try:
        settings = admin_bot._load_bot_runtime_settings()
        queue_service = admin_bot._build_queue_service_from_settings(settings)
        queues = queue_service.list_queues()
        result['queues'] = {
            'total': len(queues),
            'paused': sum(1 for queue in queues if queue.is_paused),
            'total_waiting': sum(queue.waiting_count for queue in queues),
            'total_active': sum(1 for queue in queues if queue.active_entry_id is not None),
        }
    except Exception:
        result['queues'] = {'status': 'unavailable'}
    try:
        onboarding_service = admin_bot._build_onboarding_service()
        settings = admin_bot._load_bot_runtime_settings()
        guild_id = settings.guild_id if settings else None
        if onboarding_service and guild_id:
            pending_cleanups = onboarding_service.list_pending_role_cleanups(guild_id)
            result['onboarding'] = {
                'pending_role_cleanups': len(pending_cleanups),
            }
        else:
            result['onboarding'] = {'status': 'unavailable'}
    except Exception:
        result['onboarding'] = {'status': 'unavailable'}
    try:
        settings = admin_bot._load_bot_runtime_settings()
        guild_id = admin_bot._mileage_active_guild_id(settings)
        mileage_service = admin_bot._build_mileage_service_from_settings(settings)
        tier_stats = mileage_service.list_tier_stats(guild_id)
        total_users = sum(tier_stat.user_count for tier_stat in tier_stats)
        result['mileage'] = {
            'total_users': total_users,
            'tier_count': len(tier_stats),
        }
    except Exception:
        result['mileage'] = {'status': 'unavailable'}
    return jsonify({'data': result})