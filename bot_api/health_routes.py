from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, jsonify, render_template, session, url_for

from .bot_utils import _bool_status, _health_components


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
