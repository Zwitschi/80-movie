from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, jsonify, render_template, request, session, url_for

from .bot_utils import _bool_status, _health_components, _read_bot_presence, _write_bot_presence


def build_health_snapshot() -> dict[str, object]:
    from . import admin_bot

    database_configured = bool(current_app.config.get('DATABASE_URL'))
    secret_key_configured = bool(current_app.config.get('SECRET_KEY'))
    discord_token_configured = bool(
        admin_bot._read_env('OMO_DISCORD_TOKEN', 'DISCORD_TOKEN'))
    guild_id_configured = bool(admin_bot._read_env('OMO_DISCORD_GUILD_ID'))
    oauth = admin_bot._oauth_config()
    oauth_client_id_configured = bool(oauth['client_id'])
    oauth_client_secret_configured = bool(oauth['client_secret'])
    oauth_redirect_uri_configured = bool(oauth['redirect_uri'])

    components = {
        'website_app': {
            'status': 'ok',
            'blueprint': 'bot',
            'testing': bool(current_app.config.get('TESTING')),
            'site_url': current_app.config.get('SITE_URL'),
        },
        'database': {
            'status': _bool_status(database_configured),
            'configured': database_configured,
        },
        'operator_auth': {
            'status': 'ok' if all(
                [oauth_client_id_configured, oauth_client_secret_configured,
                    oauth_redirect_uri_configured]
            ) else 'missing_config',
            'provider': 'discord-oauth',
            'client_id_configured': oauth_client_id_configured,
            'client_secret_configured': oauth_client_secret_configured,
            'redirect_uri_configured': oauth_redirect_uri_configured,
        },
        'bot_runtime': {
            'status': 'ok' if discord_token_configured else 'missing_config',
            'token_configured': discord_token_configured,
            'guild_id_configured': guild_id_configured,
            'embedded_control_room': True,
        },
        'jobs': {
            'status': 'planned',
            'scheduler_configured': False,
            'polling_worker': 'not-yet-implemented',
        },
    }

    # Add bot worker presence
    presence = _read_bot_presence()
    if presence:
        components['bot_worker'] = {
            'status': 'ok' if (presence.get('seconds_since_seen') or 999) < 120 else 'stale',
            'worker_id': presence['worker_id'],
            'last_seen_at': presence['last_seen_at'],
            'state': presence['state'],
            'seconds_since_seen': presence.get('seconds_since_seen'),
        }
    else:
        components['bot_worker'] = {
            'status': 'unavailable',
            'note': 'No presence heartbeat table or no rows yet',
        }

    overall_status = 'ok'
    if any(component['status'] == 'missing_config' for component in components.values()):
        overall_status = 'degraded'

    return {
        'status': overall_status,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'components': components,
        'summary': {
            'healthy_components': sum(1 for component in components.values() if component['status'] == 'ok'),
            'degraded_components': sum(
                1 for component in components.values() if component['status'] != 'ok'
            ),
        },
        'links': {
            'health': url_for('bot.health_api'),
            'services': url_for('bot.health_services_api'),
            'jobs': url_for('bot.health_jobs_api'),
        },
        'session': {
            'authenticated': bool(session.get(admin_bot.BOT_OPS_SESSION_KEY)),
            'scopes': session.get(admin_bot.BOT_OPS_SCOPES_SESSION_KEY, []),
            'last_seen_at': session.get(admin_bot.BOT_OPS_LAST_SEEN_AT_KEY),
        },
        'config': {
            'data_source': current_app.config.get('DATA_SOURCE'),
            'current_year': current_app.config.get('CURRENT_YEAR'),
        },
        'security': {
            'secret_key_configured': secret_key_configured,
        },
    }


def overview():
    health = build_health_snapshot()
    return render_template('index.html', health=health)


def health_page():
    from . import admin_bot

    health = build_health_snapshot()
    return render_template(
        'health.html',
        health=health,
        syndication=admin_bot.build_syndication_snapshot(),
    )


def health_api():
    return jsonify({'data': build_health_snapshot()})


def health_services_api():
    health = build_health_snapshot()
    return jsonify({'data': _health_components(health)})


def health_jobs_api():
    health = build_health_snapshot()
    return jsonify({'data': _health_components(health)['jobs']})


def operator_health_api():
    """Combined health + syndication + queue + diagnostics for operators."""
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('ops.read')
    if scope_error is not None:
        return scope_error

    health = build_health_snapshot()
    syndication = admin_bot.build_syndication_snapshot()
    queue_index = admin_bot.build_queue_index_snapshot()
    diag_resp = admin_bot.diagnostics_api()
    diagnostics_data = diag_resp.get_json() if hasattr(diag_resp, 'get_json') else {}

    return jsonify({
        'health': health,
        'syndication': {
            'status': syndication['status'],
            'summary': syndication['summary'],
            'sources': syndication['sources'],
            'bot_runtime': syndication['bot_runtime'],
        },
        'queues': queue_index,
        'diagnostics': diagnostics_data,
    })


def upsert_worker_heartbeat():
    """POST /api/worker/heartbeat — register/update bot worker presence.

    Expects JSON body with optional: worker_id, state, metadata.
    No operator authentication required.
    """
    data = request.get_json(silent=True) or {}
    worker_id = str(data.get('worker_id', 'default')).strip() or 'default'
    state = str(data.get('state', 'running')).strip() or 'running'
    metadata = data.get('metadata') if isinstance(
        data.get('metadata'), dict) else None

    success = _write_bot_presence(worker_id, state=state, metadata=metadata)
    if success:
        return jsonify({'data': {'worker_id': worker_id, 'status': 'recorded'}}), 200
    return jsonify({
        'error': {'code': 'database_unavailable', 'message': 'Could not write presence row.'}
    }), 503
