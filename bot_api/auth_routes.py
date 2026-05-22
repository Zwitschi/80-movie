from __future__ import annotations

from secrets import token_urlsafe
from typing import cast

from flask import current_app, redirect, render_template, request, session, url_for

from . import bot_operator_service
from .bot_utils import _operator_user_id, _utcnow


def require_operator_session():
    from . import admin_bot

    if current_app.config.get('TESTING'):
        return None

    allowed_endpoints = {
        'bot.login',
        'bot.oauth_start',
        'bot.oauth_callback',
    }
    if request.endpoint in allowed_endpoints:
        return None

    if not session.get(admin_bot.BOT_OPS_SESSION_KEY):
        return admin_bot._login_redirect_response()

    if admin_bot.operator_session_expired():
        admin_bot.clear_operator_session()
        return admin_bot._login_redirect_response(expired=True)

    admin_bot.refresh_operator_session_activity()

    return None


def login():
    from . import admin_bot

    error = request.args.get('error')
    if error == 'session-expired':
        error = 'Your bot operator session expired. Please sign in again.'

    return render_template(
        'login.html',
        oauth_ready=admin_bot._oauth_ready(),
        next_url=admin_bot._sanitize_next_url(request.args.get('next')),
        error=error,
    )


def oauth_start():
    from . import admin_bot

    if not admin_bot._oauth_ready():
        return render_template(
            'login.html',
            oauth_ready=False,
            next_url=admin_bot._sanitize_next_url(request.args.get('next')),
            error='Discord OAuth is not configured for bot operators yet.',
        ), 503

    state = token_urlsafe(24)
    next_url = admin_bot._sanitize_next_url(request.args.get('next'))
    session[admin_bot.BOT_OPS_OAUTH_STATE_KEY] = state
    session[admin_bot.BOT_OPS_NEXT_URL_KEY] = next_url

    oauth = admin_bot._oauth_config()
    query = admin_bot.urlencode({
        'client_id': oauth['client_id'],
        'redirect_uri': oauth['redirect_uri'],
        'response_type': 'code',
        'scope': 'identify',
        'state': state,
        'prompt': 'consent',
    })
    return redirect(f'{admin_bot.DISCORD_AUTHORIZE_URL}?{query}')


def oauth_callback():
    from . import admin_bot

    expected_state = session.get(admin_bot.BOT_OPS_OAUTH_STATE_KEY)
    state = request.args.get('state', '')
    code = request.args.get('code', '')
    if not expected_state or state != expected_state:
        return render_template(
            'login.html',
            oauth_ready=admin_bot._oauth_ready(),
            next_url=admin_bot._sanitize_next_url(session.get(admin_bot.BOT_OPS_NEXT_URL_KEY)),
            error='Operator login failed: OAuth state did not match.',
        ), 400

    if not code:
        return render_template(
            'login.html',
            oauth_ready=admin_bot._oauth_ready(),
            next_url=admin_bot._sanitize_next_url(session.get(admin_bot.BOT_OPS_NEXT_URL_KEY)),
            error='Operator login failed: Discord did not return an authorization code.',
        ), 400

    try:
        operator_identity = admin_bot.exchange_code_for_discord_identity(code)
    except admin_bot.OperatorAuthError as exc:
        return render_template(
            'login.html',
            oauth_ready=admin_bot._oauth_ready(),
            next_url=admin_bot._sanitize_next_url(session.get(admin_bot.BOT_OPS_NEXT_URL_KEY)),
            error=str(exc),
        ), 400

    user_id = _operator_user_id(operator_identity)
    operator_access = bot_operator_service.get_operator_access(user_id)

    if not operator_access['allowed']:
        return render_template(
            'login.html',
            oauth_ready=admin_bot._oauth_ready(),
            next_url=admin_bot._sanitize_next_url(session.get(admin_bot.BOT_OPS_NEXT_URL_KEY)),
            error='Operator login denied: Discord account is not on the control-room allowlist.',
        ), 403

    now_iso = _utcnow().isoformat()
    scopes = cast(list[str], operator_access['scopes'])
    bot_operator_service.persist_operator_login(
        operator_identity=operator_identity,
        scopes=scopes,
        last_login_at=_utcnow(),
    )
    session[admin_bot.BOT_OPS_SESSION_ID_KEY] = token_urlsafe(18)
    session[admin_bot.BOT_OPS_SESSION_KEY] = user_id
    session[admin_bot.BOT_OPS_SCOPES_SESSION_KEY] = scopes
    session[admin_bot.BOT_OPS_LOGIN_AT_KEY] = now_iso
    session[admin_bot.BOT_OPS_LAST_SEEN_AT_KEY] = now_iso
    session.pop(admin_bot.BOT_OPS_OAUTH_STATE_KEY, None)
    next_url = admin_bot._sanitize_next_url(session.pop(admin_bot.BOT_OPS_NEXT_URL_KEY, None))
    return redirect(next_url)


def logout():
    from . import admin_bot

    admin_bot.clear_operator_session()
    return redirect(url_for('bot.login'))