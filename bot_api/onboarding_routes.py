from __future__ import annotations

from flask import jsonify, render_template, request, session


def onboarding_page():
    return render_template(
        'onboarding.html',
        error=request.args.get('error'),
    )


def list_onboarding_events_api():
    from . import admin_bot

    if not admin_bot._operator_can('onboarding.read'):
        return admin_bot._operator_scope_denied_response('onboarding.read')
    settings = admin_bot._load_bot_runtime_settings()
    guild_id = request.args.get('guild_id', type=int) or settings.guild_id
    if not guild_id:
        return jsonify({'error': 'guild_id is required'}), 400
    limit = min(request.args.get('limit', 50, type=int), 200)
    onboarding_service = admin_bot._build_onboarding_service()
    if onboarding_service is None:
        return jsonify({'data': [], 'meta': {'guild_id': guild_id, 'backend': 'unavailable'}}), 200
    events = onboarding_service.list_recent_events(guild_id, limit=limit)
    return jsonify({
        'data': [
            {
                'event_id': event.event_id,
                'guild_id': event.guild_id,
                'discord_user_id': event.discord_user_id,
                'display_name': event.display_name,
                'event_type': event.event_type,
                'role_id': event.role_id,
                'role_binding_key': event.role_binding_key,
                'actor_user_id': event.actor_user_id,
                'metadata': event.metadata,
                'created_at': event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
        'meta': {'guild_id': guild_id, 'count': len(events)},
    })


def replay_onboarding_api():
    from . import admin_bot

    if not admin_bot._operator_can('onboarding.write'):
        return admin_bot._operator_scope_denied_response('onboarding.write')
    body = request.get_json(silent=True) or {}
    guild_id = body.get('guild_id')
    discord_user_id = body.get('discord_user_id')
    display_name = body.get('display_name', '')
    actor_user_id = str(session.get(admin_bot.BOT_OPS_SESSION_KEY, '')).strip() or None
    if not guild_id or not discord_user_id:
        return jsonify({'error': 'guild_id and discord_user_id are required'}), 400
    onboarding_service = admin_bot._build_onboarding_service()
    if onboarding_service is None:
        return jsonify({'error': 'Onboarding service unavailable — database not configured'}), 503
    events, was_skipped = onboarding_service.replay_member_onboarding(
        guild_id=int(guild_id),
        discord_user_id=str(discord_user_id),
        display_name=str(display_name),
        actor_user_id=str(actor_user_id or ''),
    )
    audit_service = admin_bot._build_bot_audit_service()
    if audit_service:
        try:
            audit_service.record(
                action_key='onboarding.replay',
                target_type='member',
                target_key=str(discord_user_id),
                before_state=None,
                after_state={'replayed_events': len(events), 'skipped': was_skipped},
            )
        except Exception:
            pass
    return jsonify({
        'data': {
            'skipped': was_skipped,
            'replayed_events': len(events),
            'events': [
                {
                    'event_id': event.event_id,
                    'event_type': event.event_type,
                    'role_id': event.role_id,
                    'role_binding_key': event.role_binding_key,
                }
                for event in events
            ],
        },
        'meta': {'guild_id': guild_id, 'discord_user_id': discord_user_id},
    })


def reset_onboarding_api():
    from . import admin_bot

    if not admin_bot._operator_can('onboarding.write'):
        return admin_bot._operator_scope_denied_response('onboarding.write')
    body = request.get_json(silent=True) or {}
    guild_id = body.get('guild_id')
    discord_user_id = body.get('discord_user_id')
    display_name = body.get('display_name', '')
    dry_run = bool(body.get('dry_run', False))
    confirm = str(body.get('confirm') or '').strip().lower()
    actor_user_id = str(session.get(admin_bot.BOT_OPS_SESSION_KEY, '')).strip() or None
    if not guild_id or not discord_user_id:
        return jsonify({'error': 'guild_id and discord_user_id are required'}), 400
    if not actor_user_id:
        return jsonify({'error': 'operator session is required for onboarding reset'}), 401
    if not dry_run and confirm != 'reset':
        return jsonify({'error': 'Onboarding reset requires confirm=reset.'}), 400
    onboarding_service = admin_bot._build_onboarding_service()
    if onboarding_service is None:
        return jsonify({'error': 'Onboarding service unavailable — database not configured'}), 503
    events, deleted_count = onboarding_service.reset_member_onboarding(
        guild_id=int(guild_id),
        discord_user_id=str(discord_user_id),
        display_name=str(display_name),
        actor_user_id=actor_user_id,
        dry_run=dry_run,
    )
    if not dry_run:
        audit_service = admin_bot._build_bot_audit_service()
        if audit_service:
            try:
                audit_service.record(
                    action_key='onboarding.reset',
                    target_type='member',
                    target_key=str(discord_user_id),
                    before_state={'deleted_events': deleted_count},
                    after_state={'replayed_events': len(events)},
                )
            except Exception:
                pass
    return jsonify({
        'data': {
            'deleted_events': deleted_count,
            'replayed_events': len(events),
            'dry_run': dry_run,
            'events': [
                {
                    'event_id': event.event_id,
                    'event_type': event.event_type,
                    'role_id': event.role_id,
                    'role_binding_key': event.role_binding_key,
                }
                for event in events
            ],
        },
        'meta': {'guild_id': guild_id, 'discord_user_id': discord_user_id},
    })


def request_onboarding_role_cleanup_api():
    from . import admin_bot

    if not admin_bot._operator_can('onboarding.write'):
        return admin_bot._operator_scope_denied_response('onboarding.write')
    body = request.get_json(silent=True) or {}
    guild_id = body.get('guild_id')
    discord_user_id = body.get('discord_user_id')
    display_name = str(body.get('display_name') or '').strip()
    actor_user_id = str(session.get(admin_bot.BOT_OPS_SESSION_KEY, '')).strip() or None
    if not guild_id or not discord_user_id:
        return jsonify({'error': 'guild_id and discord_user_id are required'}), 400
    if not actor_user_id:
        return jsonify({'error': 'operator session is required'}), 401
    onboarding_service = admin_bot._build_onboarding_service()
    if onboarding_service is None:
        return jsonify({'error': 'Onboarding service unavailable — database not configured'}), 503
    event = onboarding_service.request_role_cleanup(
        guild_id=int(guild_id),
        discord_user_id=str(discord_user_id),
        display_name=display_name or str(discord_user_id),
        actor_user_id=actor_user_id,
    )
    admin_bot._record_bot_audit_event(
        action_key='onboarding.role_cleanup_requested',
        target_type='member',
        target_key=str(discord_user_id),
        before_state={},
        after_state={'event_id': event.event_id},
    )
    return jsonify({
        'data': {
            'event_id': event.event_id,
            'event_type': event.event_type,
            'discord_user_id': event.discord_user_id,
            'guild_id': event.guild_id,
        },
    })