from __future__ import annotations

import json
import os
from secrets import token_urlsafe
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from . import bot_operator_repo
from . import bot_operator_service


admin_bot_blueprint = Blueprint('admin_bot', __name__, url_prefix='/admin/bot')

BOT_OPS_SESSION_KEY = 'bot_ops_user_id'
BOT_OPS_SESSION_ID_KEY = 'bot_ops_session_id'
BOT_OPS_SCOPES_SESSION_KEY = 'bot_ops_scopes'
BOT_OPS_LOGIN_AT_KEY = 'bot_ops_login_at'
BOT_OPS_LAST_SEEN_AT_KEY = 'bot_ops_last_seen_at'
BOT_OPS_OAUTH_STATE_KEY = 'bot_ops_oauth_state'
BOT_OPS_NEXT_URL_KEY = 'bot_ops_next_url'

DISCORD_AUTHORIZE_URL = 'https://discord.com/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'
DISCORD_ME_URL = 'https://discord.com/api/users/@me'


class OperatorAuthError(RuntimeError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bool_status(configured: bool) -> str:
    return 'ok' if configured else 'missing_config'


def _read_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def _oauth_config() -> dict[str, str]:
    return {
        'client_id': str(current_app.config.get('BOT_OPS_DISCORD_CLIENT_ID', '')).strip(),
        'client_secret': str(current_app.config.get('BOT_OPS_DISCORD_CLIENT_SECRET', '')).strip(),
        'redirect_uri': str(current_app.config.get('BOT_OPS_DISCORD_REDIRECT_URI', '')).strip(),
    }


def _oauth_ready() -> bool:
    config = _oauth_config()
    return all(config.values())


def _operator_user_id(operator_identity: dict[str, object]) -> str:
    return str(operator_identity.get('user_id', '')).strip()


def _sanitize_next_url(next_url: str | None) -> str:
    if next_url and next_url.startswith('/admin/bot') and not next_url.startswith('//'):
        return next_url
    return url_for('admin_bot.overview')


def _operator_session_keys() -> tuple[str, ...]:
    return (
        BOT_OPS_SESSION_KEY,
        BOT_OPS_SESSION_ID_KEY,
        BOT_OPS_SCOPES_SESSION_KEY,
        BOT_OPS_LOGIN_AT_KEY,
        BOT_OPS_LAST_SEEN_AT_KEY,
        BOT_OPS_OAUTH_STATE_KEY,
        BOT_OPS_NEXT_URL_KEY,
    )


def clear_operator_session() -> None:
    for key in _operator_session_keys():
        session.pop(key, None)


def _session_idle_timeout() -> timedelta:
    minutes = int(current_app.config.get('BOT_OPS_SESSION_IDLE_MINUTES', 60))
    return timedelta(minutes=max(minutes, 1))


def _parse_session_timestamp(raw_value: object) -> datetime | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None

    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def operator_session_expired() -> bool:
    last_seen_at = _parse_session_timestamp(
        session.get(BOT_OPS_LAST_SEEN_AT_KEY))
    if last_seen_at is None:
        return True
    return _utcnow() - last_seen_at > _session_idle_timeout()


def refresh_operator_session_activity() -> None:
    session[BOT_OPS_LAST_SEEN_AT_KEY] = _utcnow().isoformat()


def _discord_avatar_url(discord_user: dict[str, object]) -> str | None:
    user_id = str(discord_user.get('id', '')).strip()
    avatar_hash = str(discord_user.get('avatar', '')).strip()
    if not user_id or not avatar_hash:
        return None
    return f'https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png'


def exchange_code_for_discord_identity(code: str) -> dict[str, object]:
    oauth = _oauth_config()
    if not all(oauth.values()):
        raise OperatorAuthError(
            'Discord OAuth is not configured for bot operators.')

    token_body = urlencode({
        'client_id': oauth['client_id'],
        'client_secret': oauth['client_secret'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': oauth['redirect_uri'],
    }).encode('utf-8')

    token_request = Request(
        DISCORD_TOKEN_URL,
        data=token_body,
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        method='POST',
    )
    with urlopen(token_request, timeout=10) as response:
        token_payload = json.loads(response.read().decode('utf-8'))

    access_token = str(token_payload.get('access_token', '')).strip()
    if not access_token:
        raise OperatorAuthError(
            'Discord OAuth token exchange did not return an access token.')

    identity_request = Request(
        DISCORD_ME_URL,
        headers={
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
        },
        method='GET',
    )
    with urlopen(identity_request, timeout=10) as response:
        identity_payload = json.loads(response.read().decode('utf-8'))

    user_id = str(identity_payload.get('id', '')).strip()
    if not user_id:
        raise OperatorAuthError(
            'Discord OAuth identity response did not include a user id.')

    return {
        'user_id': user_id,
        'username': identity_payload.get('username', ''),
        'global_name': identity_payload.get('global_name', ''),
        'avatar_url': _discord_avatar_url(identity_payload),
    }


def build_health_snapshot() -> dict[str, object]:
    database_configured = bool(current_app.config.get('DATABASE_URL'))
    secret_key_configured = bool(current_app.config.get('SECRET_KEY'))
    discord_token_configured = bool(
        _read_env('OMO_DISCORD_TOKEN', 'DISCORD_TOKEN'))
    guild_id_configured = bool(_read_env('OMO_DISCORD_GUILD_ID'))
    oauth = _oauth_config()
    oauth_client_id_configured = bool(oauth['client_id'])
    oauth_client_secret_configured = bool(oauth['client_secret'])
    oauth_redirect_uri_configured = bool(oauth['redirect_uri'])

    components = {
        'website_app': {
            'status': 'ok',
            'blueprint': admin_bot_blueprint.name,
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
            'health': url_for('admin_bot.health_api'),
            'services': url_for('admin_bot.health_services_api'),
            'jobs': url_for('admin_bot.health_jobs_api'),
        },
        'session': {
            'authenticated': bool(session.get(BOT_OPS_SESSION_KEY)),
            'scopes': session.get(BOT_OPS_SCOPES_SESSION_KEY, []),
            'last_seen_at': session.get(BOT_OPS_LAST_SEEN_AT_KEY),
        },
        'config': {
            'data_source': current_app.config.get('DATA_SOURCE'),
            'current_year': current_app.config.get('CURRENT_YEAR'),
        },
        'security': {
            'secret_key_configured': secret_key_configured,
        },
    }


def _health_components(health: dict[str, object]) -> dict[str, Any]:
    return cast(dict[str, Any], health['components'])


def _login_redirect_response(expired: bool = False):
    if request.path.startswith('/admin/bot/api/'):
        return jsonify({
            'error': {
                'code': 'operator_session_expired' if expired else 'operator_auth_required',
                'message': (
                    'Operator session expired for control-room API access.'
                    if expired else
                    'Operator login is required for control-room API access.'
                ),
            }
        }), 401

    return redirect(
        url_for(
            'admin_bot.login',
            next=request.url,
            error='session-expired' if expired else None,
        )
    )


def _operator_scope_denied_response(*required_scopes: str):
    if request.path.startswith('/admin/bot/api/'):
        return jsonify({
            'error': {
                'code': 'operator_scope_required',
                'message': 'Operator session is missing a required scope for this action.',
                'required_scopes': list(required_scopes),
            }
        }), 403

    return jsonify({
        'error': {
            'code': 'operator_scope_required',
            'message': 'Operator session is missing a required scope for this action.',
            'required_scopes': list(required_scopes),
        }
    }), 403


def require_operator_scope(*required_scopes: str):
    if bot_operator_service.has_operator_scope(
        session.get(BOT_OPS_SCOPES_SESSION_KEY, []),
        *required_scopes,
    ):
        return None
    return _operator_scope_denied_response(*required_scopes)


def _operator_not_found_response():
    if request.path.startswith('/admin/bot/api/'):
        return jsonify({
            'error': {
                'code': 'operator_not_found',
                'message': 'Bot operator record was not found.',
            }
        }), 404

    return redirect(url_for('admin_bot.operators_page', error='operator-not-found'))


def _invalid_operator_scopes_response():
    if request.path.startswith('/admin/bot/api/'):
        return jsonify({
            'error': {
                'code': 'invalid_operator_scopes',
                'message': 'At least one valid operator scope is required.',
            }
        }), 400

    return redirect(url_for('admin_bot.operators_page', error='invalid-operator-scopes'))


def _update_operator_active(user_id: str, is_active: bool):
    scope_error = require_operator_scope('operators.write')
    if scope_error is not None:
        return scope_error

    operator_record = bot_operator_repo.set_bot_operator_active(
        user_id, is_active)
    if operator_record is None:
        return _operator_not_found_response()
    return operator_record


def _update_operator_scopes(user_id: str, raw_scopes: object):
    scope_error = require_operator_scope('operators.write')
    if scope_error is not None:
        return scope_error

    scopes = bot_operator_service.normalize_operator_scopes(raw_scopes)
    if not scopes:
        return _invalid_operator_scopes_response()

    operator_record = bot_operator_repo.set_bot_operator_scopes(
        user_id, scopes)
    if operator_record is None:
        return _operator_not_found_response()
    return operator_record


@admin_bot_blueprint.before_request
def require_operator_session():
    if current_app.config.get('TESTING'):
        return None

    allowed_endpoints = {
        'admin_bot.login',
        'admin_bot.oauth_start',
        'admin_bot.oauth_callback',
    }
    if request.endpoint in allowed_endpoints:
        return None

    if not session.get(BOT_OPS_SESSION_KEY):
        return _login_redirect_response()

    if operator_session_expired():
        clear_operator_session()
        return _login_redirect_response(expired=True)

    refresh_operator_session_activity()

    return None


@admin_bot_blueprint.get('/login')
def login():
    error = request.args.get('error')
    if error == 'session-expired':
        error = 'Your bot operator session expired. Please sign in again.'

    return render_template(
        'admin/bot/login.html',
        oauth_ready=_oauth_ready(),
        next_url=_sanitize_next_url(request.args.get('next')),
        error=error,
    )


@admin_bot_blueprint.get('/oauth/start')
def oauth_start():
    if not _oauth_ready():
        return render_template(
            'admin/bot/login.html',
            oauth_ready=False,
            next_url=_sanitize_next_url(request.args.get('next')),
            error='Discord OAuth is not configured for bot operators yet.',
        ), 503

    state = token_urlsafe(24)
    next_url = _sanitize_next_url(request.args.get('next'))
    session[BOT_OPS_OAUTH_STATE_KEY] = state
    session[BOT_OPS_NEXT_URL_KEY] = next_url

    oauth = _oauth_config()
    query = urlencode({
        'client_id': oauth['client_id'],
        'redirect_uri': oauth['redirect_uri'],
        'response_type': 'code',
        'scope': 'identify',
        'state': state,
        'prompt': 'consent',
    })
    return redirect(f'{DISCORD_AUTHORIZE_URL}?{query}')


@admin_bot_blueprint.get('/oauth/callback')
def oauth_callback():
    expected_state = session.get(BOT_OPS_OAUTH_STATE_KEY)
    state = request.args.get('state', '')
    code = request.args.get('code', '')
    if not expected_state or state != expected_state:
        return render_template(
            'admin/bot/login.html',
            oauth_ready=_oauth_ready(),
            next_url=_sanitize_next_url(session.get(BOT_OPS_NEXT_URL_KEY)),
            error='Operator login failed: OAuth state did not match.',
        ), 400

    if not code:
        return render_template(
            'admin/bot/login.html',
            oauth_ready=_oauth_ready(),
            next_url=_sanitize_next_url(session.get(BOT_OPS_NEXT_URL_KEY)),
            error='Operator login failed: Discord did not return an authorization code.',
        ), 400

    try:
        operator_identity = exchange_code_for_discord_identity(code)
    except OperatorAuthError as exc:
        return render_template(
            'admin/bot/login.html',
            oauth_ready=_oauth_ready(),
            next_url=_sanitize_next_url(session.get(BOT_OPS_NEXT_URL_KEY)),
            error=str(exc),
        ), 400

    user_id = _operator_user_id(operator_identity)
    operator_access = bot_operator_service.get_operator_access(user_id)

    if not operator_access['allowed']:
        return render_template(
            'admin/bot/login.html',
            oauth_ready=_oauth_ready(),
            next_url=_sanitize_next_url(session.get(BOT_OPS_NEXT_URL_KEY)),
            error='Operator login denied: Discord account is not on the control-room allowlist.',
        ), 403

    now_iso = _utcnow().isoformat()
    scopes = cast(list[str], operator_access['scopes'])
    bot_operator_service.persist_operator_login(
        operator_identity=operator_identity,
        scopes=scopes,
        last_login_at=_utcnow(),
    )
    session[BOT_OPS_SESSION_ID_KEY] = token_urlsafe(18)
    session[BOT_OPS_SESSION_KEY] = user_id
    session[BOT_OPS_SCOPES_SESSION_KEY] = scopes
    session[BOT_OPS_LOGIN_AT_KEY] = now_iso
    session[BOT_OPS_LAST_SEEN_AT_KEY] = now_iso
    session.pop(BOT_OPS_OAUTH_STATE_KEY, None)
    next_url = _sanitize_next_url(session.pop(BOT_OPS_NEXT_URL_KEY, None))
    return redirect(next_url)


@admin_bot_blueprint.post('/logout')
def logout():
    clear_operator_session()
    return redirect(url_for('admin_bot.login'))


@admin_bot_blueprint.get('')
@admin_bot_blueprint.get('/')
def overview():
    health = build_health_snapshot()
    return render_template('admin/bot/index.html', health=health)


@admin_bot_blueprint.get('/health')
def health_page():
    health = build_health_snapshot()
    return render_template('admin/bot/health.html', health=health)


@admin_bot_blueprint.get('/api/health')
def health_api():
    return jsonify({'data': build_health_snapshot()})


@admin_bot_blueprint.get('/api/health/services')
def health_services_api():
    health = build_health_snapshot()
    return jsonify({'data': _health_components(health)})


@admin_bot_blueprint.get('/api/health/jobs')
def health_jobs_api():
    health = build_health_snapshot()
    return jsonify({'data': _health_components(health)['jobs']})


@admin_bot_blueprint.get('/operators')
def operators_page():
    return render_template(
        'admin/bot/operators.html',
        operators=bot_operator_repo.list_bot_operators(),
        save_success=request.args.get('saved') == '1',
        error=request.args.get('error'),
    )


@admin_bot_blueprint.get('/api/operators')
def operators_api():
    return jsonify({'data': bot_operator_repo.list_bot_operators()})


@admin_bot_blueprint.post('/api/operators/<user_id>/disable')
def disable_operator_api(user_id: str):
    operator_record = _update_operator_active(user_id, False)
    if not isinstance(operator_record, dict):
        return operator_record
    return jsonify({'data': operator_record})


@admin_bot_blueprint.post('/operators/<user_id>/disable')
def disable_operator_page_action(user_id: str):
    operator_record = _update_operator_active(user_id, False)
    if not isinstance(operator_record, dict):
        return operator_record
    return redirect(url_for('admin_bot.operators_page', saved='1'))


@admin_bot_blueprint.post('/api/operators/<user_id>/enable')
def enable_operator_api(user_id: str):
    operator_record = _update_operator_active(user_id, True)
    if not isinstance(operator_record, dict):
        return operator_record
    return jsonify({'data': operator_record})


@admin_bot_blueprint.post('/api/operators/<user_id>/scopes')
def update_operator_scopes_api(user_id: str):
    raw_scopes = request.get_json(silent=True, cache=False)
    if isinstance(raw_scopes, dict):
        raw_scopes = raw_scopes.get('scopes')
    else:
        raw_scopes = request.form.get('scopes', '')

    operator_record = _update_operator_scopes(user_id, raw_scopes)
    if not isinstance(operator_record, dict):
        return operator_record
    return jsonify({'data': operator_record})


@admin_bot_blueprint.post('/operators/<user_id>/enable')
def enable_operator_page_action(user_id: str):
    operator_record = _update_operator_active(user_id, True)
    if not isinstance(operator_record, dict):
        return operator_record
    return redirect(url_for('admin_bot.operators_page', saved='1'))


@admin_bot_blueprint.post('/operators/<user_id>/scopes')
def update_operator_scopes_page_action(user_id: str):
    operator_record = _update_operator_scopes(
        user_id, request.form.get('scopes', ''))
    if not isinstance(operator_record, dict):
        return operator_record
    return redirect(url_for('admin_bot.operators_page', saved='1'))
