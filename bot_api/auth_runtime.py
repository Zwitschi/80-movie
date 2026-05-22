from __future__ import annotations

import json
import os
from secrets import token_urlsafe
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request


def _audit_database_url() -> str | None:
    from . import admin_bot

    try:
        settings = admin_bot._load_bot_runtime_settings()
    except admin_bot.ConfigError:
        settings = None

    if settings and settings.database_url:
        return settings.database_url
    return str(admin_bot.current_app.config.get('DATABASE_URL') or '').strip() or None


def _build_bot_audit_service():
    from . import admin_bot

    database_url = admin_bot._audit_database_url()
    if not database_url:
        return None
    return admin_bot.BotAuditService(
        admin_bot.build_postgres_bot_audit_log_repository(database_url)
    )


def _mark_bot_audit_degraded() -> None:
    from . import admin_bot

    if admin_bot.has_request_context():
        admin_bot.request.environ[admin_bot._BOT_AUDIT_STATUS_ENV_KEY] = 'degraded'


def _record_bot_audit_event(
    *,
    action_key: str,
    target_type: str,
    target_key: str,
    before_state: object,
    after_state: object,
) -> None:
    from . import admin_bot

    try:
        audit_service = admin_bot._build_bot_audit_service()
        if audit_service is None:
            return
        audit_service.record(
            actor_user_id=str(admin_bot.session.get(
                admin_bot.BOT_OPS_SESSION_KEY, '')).strip() or None,
            actor_session_id=str(admin_bot.session.get(
                admin_bot.BOT_OPS_SESSION_ID_KEY, '')).strip() or None,
            action_key=action_key,
            target_type=target_type,
            target_key=target_key,
            request_id=admin_bot.request.headers.get(
                'X-Request-Id') or token_urlsafe(8),
            before_state=admin_bot._serialize_audit_state(before_state),
            after_state=admin_bot._serialize_audit_state(after_state),
        )
    except Exception:
        admin_bot._mark_bot_audit_degraded()
        if admin_bot.has_app_context():
            admin_bot.current_app.logger.warning(
                'Bot audit logging degraded for %s:%s',
                target_type,
                target_key,
                exc_info=True,
            )


def _apply_bot_audit_status(response):
    from . import admin_bot

    audit_status = admin_bot.request.environ.get(
        admin_bot._BOT_AUDIT_STATUS_ENV_KEY
    ) if admin_bot.has_request_context() else None
    if audit_status:
        response.headers[admin_bot.BOT_AUDIT_STATUS_HEADER] = str(audit_status)
    return response


def _read_env(*keys: str) -> str:
    from . import admin_bot

    for key in keys:
        value = str(admin_bot.current_app.config.get(
            key) or os.getenv(key) or '').strip()
        if value:
            return value
    return ''


def _oauth_config() -> dict[str, str]:
    from . import admin_bot

    return {
        'client_id': admin_bot._read_env(
            'BOT_OPS_DISCORD_CLIENT_ID',
            'OMO_DISCORD_CLIENT_ID',
            'DISCORD_CLIENT_ID',
        ),
        'client_secret': admin_bot._read_env(
            'BOT_OPS_DISCORD_CLIENT_SECRET',
            'OMO_DISCORD_CLIENT_SECRET',
            'DISCORD_CLIENT_SECRET',
        ),
        'redirect_uri': admin_bot._read_env(
            'BOT_OPS_DISCORD_REDIRECT_URI',
            'OMO_DISCORD_REDIRECT_URI',
            'DISCORD_REDIRECT_URI',
        ),
    }


def _oauth_ready() -> bool:
    from . import admin_bot

    oauth = admin_bot._oauth_config()
    return all(oauth.values())


def _sanitize_next_url(next_url: object) -> str:
    from . import admin_bot

    candidate = str(next_url or '').strip()
    if candidate.startswith('/') and not candidate.startswith('//'):
        return candidate
    return admin_bot.url_for('bot.overview')


def exchange_code_for_discord_identity(code: str) -> dict[str, object]:
    from . import admin_bot

    oauth = admin_bot._oauth_config()
    if not all(oauth.values()):
        raise admin_bot.OperatorAuthError(
            'Discord OAuth is not configured for bot operators.'
        )

    token_body = urlencode({
        'client_id': oauth['client_id'],
        'client_secret': oauth['client_secret'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': oauth['redirect_uri'],
    }).encode('utf-8')

    token_request = Request(
        admin_bot.DISCORD_TOKEN_URL,
        data=token_body,
        headers={
            **admin_bot._discord_request_headers(),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        method='POST',
    )
    try:
        with admin_bot.urlopen(token_request, timeout=10) as response:
            token_payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        detail = admin_bot._decode_http_error(exc)
        if detail:
            raise admin_bot.OperatorAuthError(
                f'Discord OAuth token exchange failed with HTTP {exc.code}: {detail}'
            ) from exc
        raise admin_bot.OperatorAuthError(
            f'Discord OAuth token exchange failed with HTTP {exc.code}.'
        ) from exc
    except URLError as exc:
        raise admin_bot.OperatorAuthError(
            'Discord OAuth token exchange failed because Discord could not be reached.'
        ) from exc

    access_token = str(token_payload.get('access_token', '')).strip()
    if not access_token:
        raise admin_bot.OperatorAuthError(
            'Discord OAuth token exchange did not return an access token.'
        )

    identity_request = Request(
        admin_bot.DISCORD_ME_URL,
        headers=admin_bot._discord_request_headers(access_token=access_token),
        method='GET',
    )
    try:
        with admin_bot.urlopen(identity_request, timeout=10) as response:
            identity_payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        detail = admin_bot._decode_http_error(exc)
        if detail:
            raise admin_bot.OperatorAuthError(
                f'Discord OAuth identity lookup failed with HTTP {exc.code}: {detail}'
            ) from exc
        raise admin_bot.OperatorAuthError(
            f'Discord OAuth identity lookup failed with HTTP {exc.code}.'
        ) from exc
    except URLError as exc:
        raise admin_bot.OperatorAuthError(
            'Discord OAuth identity lookup failed because Discord could not be reached.'
        ) from exc

    user_id = str(identity_payload.get('id', '')).strip()
    if not user_id:
        raise admin_bot.OperatorAuthError(
            'Discord OAuth identity response did not include a user id.'
        )

    return {
        'user_id': user_id,
        'username': identity_payload.get('username', ''),
        'global_name': identity_payload.get('global_name', ''),
        'avatar_url': admin_bot._discord_avatar_url(identity_payload),
    }
