from __future__ import annotations

import json
import os
from secrets import token_urlsafe
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, has_app_context, has_request_context, jsonify, redirect, render_template, request, session, url_for

# Bot imports are deferred so the website can start even when deployed
# from the website/ subdirectory (where bot/ is not on the Python path).
# When bot/ is available (repo-root deploy or PYTHONPATH includes root),
# these imports resolve normally.
try:
    from bot.omo_bot.config import BotConfig
    from bot.omo_bot.config import BotRuntimeSettings, ConfigError, read_runtime_settings
    from bot.omo_bot.jobs import SyndicationPollingJob
    from bot.omo_bot.main import build_syndication_adapters
    from bot.omo_bot.models import MileageEvent, MileageTierStat, MileageTotal, MileageUserDetail, OnboardingConfig, OnboardingEvent, OnboardingRoleBinding, QueueEntry, QueueEvent, QueueSnapshot, QueueSummary, SyndicationSourceState
    from bot.omo_bot.repositories import (
        build_postgres_bot_audit_log_repository,
        build_postgres_bot_config_repository,
        build_postgres_mileage_repository,
        build_postgres_onboarding_repository,
        build_postgres_queue_repository,
        build_postgres_syndication_repository,
    )
    from bot.omo_bot.services import BotAuditService, NullSyndicationDeliverySink, SyndicationPlanningService
    from bot.omo_bot.services.onboarding_service import OnboardingService
    from bot.omo_bot.services.mileage_service import (
        MileageConflictError,
        MileageNotFoundError,
        MileageService,
        MileageValidationError,
    )
    from bot.omo_bot.services.queue_service import (
        QueueConflictError,
        QueueEntryNotFoundError,
        QueueNotFoundError,
        QueuePausedError,
        QueueService,
        QueueValidationError,
    )
    BOT_MODULE_AVAILABLE = True
except ModuleNotFoundError:
    BOT_MODULE_AVAILABLE = False
    BotConfig = None  # type: ignore[misc,assignment]
    BotRuntimeSettings = None  # type: ignore[misc,assignment]
    ConfigError = RuntimeError  # type: ignore[misc,assignment]
    SyndicationPollingJob = None  # type: ignore[misc,assignment]
    build_syndication_adapters = None  # type: ignore[misc,assignment]
    MileageEvent = None  # type: ignore[misc,assignment]
    MileageTierStat = None  # type: ignore[misc,assignment]
    MileageTotal = None  # type: ignore[misc,assignment]
    MileageUserDetail = None  # type: ignore[misc,assignment]
    OnboardingConfig = None  # type: ignore[misc,assignment]
    OnboardingEvent = None  # type: ignore[misc,assignment]
    OnboardingRoleBinding = None  # type: ignore[misc,assignment]
    QueueEntry = None  # type: ignore[misc,assignment]
    QueueEvent = None  # type: ignore[misc,assignment]
    QueueSnapshot = None  # type: ignore[misc,assignment]
    QueueSummary = None  # type: ignore[misc,assignment]
    SyndicationSourceState = None  # type: ignore[misc,assignment]
    # type: ignore[misc,assignment]
    build_postgres_bot_audit_log_repository = None
    # type: ignore[misc,assignment]
    build_postgres_bot_config_repository = None
    build_postgres_mileage_repository = None  # type: ignore[misc,assignment]
    # type: ignore[misc,assignment]
    build_postgres_onboarding_repository = None
    build_postgres_queue_repository = None  # type: ignore[misc,assignment]
    # type: ignore[misc,assignment]
    build_postgres_syndication_repository = None
    BotAuditService = None  # type: ignore[misc,assignment]
    NullSyndicationDeliverySink = None  # type: ignore[misc,assignment]
    SyndicationPlanningService = None  # type: ignore[misc,assignment]
    OnboardingService = None  # type: ignore[misc,assignment]
    MileageConflictError = RuntimeError  # type: ignore[misc,assignment]
    MileageNotFoundError = RuntimeError  # type: ignore[misc,assignment]
    MileageService = None  # type: ignore[misc,assignment]
    MileageValidationError = RuntimeError  # type: ignore[misc,assignment]
    QueueConflictError = RuntimeError  # type: ignore[misc,assignment]
    QueueEntryNotFoundError = RuntimeError  # type: ignore[misc,assignment]
    QueueNotFoundError = RuntimeError  # type: ignore[misc,assignment]
    QueuePausedError = RuntimeError  # type: ignore[misc,assignment]
    QueueService = None  # type: ignore[misc,assignment]
    QueueValidationError = RuntimeError  # type: ignore[misc,assignment]

    def read_runtime_settings(env=None):  # type: ignore[misc]
        raise RuntimeError('Bot module not available on this deployment path.')

from . import bot_operator_repo
from . import bot_operator_service
from .bot_utils import (
    DISCORD_HTTP_USER_AGENT,
    _bool_status,
    _build_bot_config_from_runtime_settings,
    _configured_syndication_source,
    _decode_http_error,
    _default_syndication_state,
    _discord_avatar_url,
    _discord_request_headers,
    _health_components,
    _manual_syndication_actions_supported,
    _mileage_active_guild_id,
    _operator_user_id,
    _parse_session_timestamp,
    _serialize_audit_state,
    _serialize_audit_value,
    _syndication_last_poll_result,
    _syndication_source_status,
    _syndication_summary,
    _utcnow,
)
from .health_routes import (
    build_health_snapshot,
    overview,
    health_page,
    health_api,
    health_services_api,
    health_jobs_api,
)
from .auth_routes import (
    require_operator_session,
    login,
    oauth_start,
    oauth_callback,
    logout,
)
from .operator_routes import (
    operators_page,
    operators_api,
    disable_operator_api,
    disable_operator_page_action,
    enable_operator_api,
    enable_operator_page_action,
    update_operator_scopes_api,
    update_operator_scopes_page_action,
)
from .queue_routes import (
    queues_page,
    queue_detail_page,
    queues_api,
    queue_detail_api,
    queue_events_api,
    create_queue_api,
    create_queue_page_action,
    advance_queue_api,
    advance_queue_page_action,
    remove_queue_entry_api,
    remove_queue_entry_page_action,
    move_queue_entry_api,
    move_queue_entry_page_action,
    pause_queue_api,
    pause_queue_page_action,
    resume_queue_api,
    resume_queue_page_action,
    clear_queue_api,
    clear_queue_page_action,
)
from .mileage_routes import (
    mileage_page,
    mileage_detail_page,
    mileage_users_api,
    mileage_user_detail_api,
    mileage_user_events_api,
    mileage_tiers_api,
    adjust_mileage_user_api,
    adjust_mileage_user_page_action,
    reverse_mileage_event_api,
    reverse_mileage_event_page_action,
)
from .config_routes import (
    config_page,
    config_api,
    set_active_guild_api,
    set_active_guild_page_action,
    upsert_channel_binding_api,
    upsert_channel_binding_page_action,
    delete_channel_binding_api,
    delete_channel_binding_page_action,
    upsert_role_binding_api,
    upsert_role_binding_page_action,
    delete_role_binding_api,
    delete_role_binding_page_action,
    enable_syndication_source_api,
    enable_syndication_source_page_action,
    disable_syndication_source_api,
    disable_syndication_source_page_action,
)
from .syndication_routes import (
    syndication_page,
    syndication_api,
    syndication_sources_api,
    syndication_channels_api,
    retry_syndication_source_api,
    retry_syndication_source_page_action,
    reset_syndication_checkpoint_api,
    reset_syndication_checkpoint_page_action,
)
from .command_routes import (
    commands_page,
    commands_api,
    poll_all_sources_api,
    poll_all_sources_page_action,
)
from .diagnostics_routes import diagnostics_api
from .onboarding_routes import (
    onboarding_page,
    list_onboarding_events_api,
    replay_onboarding_api,
    reset_onboarding_api,
    request_onboarding_role_cleanup_api,
)
from .runtime_snapshot import (
    _build_bot_config_repository_from_settings,
    _effective_runtime_settings,
    _config_write_supported,
    _build_syndication_repository_from_settings,
    _build_manual_syndication_polling_job,
    _serialize_syndication_state,
    build_syndication_snapshot,
    build_bot_configuration_snapshot,
    build_bot_commands_snapshot,
    _run_manual_syndication_poll_all,
)


bp = Blueprint('bot', __name__, url_prefix='/bot')

BOT_AUDIT_STATUS_HEADER = 'X-OMO-Bot-Audit-Status'
_BOT_AUDIT_STATUS_ENV_KEY = 'omo.bot.audit_status'

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


def _audit_database_url() -> str | None:
    try:
        settings = _load_bot_runtime_settings()
    except ConfigError:
        settings = None

    if settings and settings.database_url:
        return settings.database_url
    return str(current_app.config.get('DATABASE_URL') or '').strip() or None


def _build_bot_audit_service() -> BotAuditService | None:
    database_url = _audit_database_url()
    if not database_url:
        return None
    return BotAuditService(build_postgres_bot_audit_log_repository(database_url))


def _mark_bot_audit_degraded() -> None:
    if has_request_context():
        request.environ[_BOT_AUDIT_STATUS_ENV_KEY] = 'degraded'


def _record_bot_audit_event(
    *,
    action_key: str,
    target_type: str,
    target_key: str,
    before_state: object,
    after_state: object,
) -> None:
    try:
        audit_service = _build_bot_audit_service()
        if audit_service is None:
            return
        audit_service.record(
            actor_user_id=str(session.get(
                BOT_OPS_SESSION_KEY, '')).strip() or None,
            actor_session_id=str(session.get(
                BOT_OPS_SESSION_ID_KEY, '')).strip() or None,
            action_key=action_key,
            target_type=target_type,
            target_key=target_key,
            request_id=request.headers.get('X-Request-Id') or token_urlsafe(8),
            before_state=_serialize_audit_state(before_state),
            after_state=_serialize_audit_state(after_state),
        )
    except Exception:
        _mark_bot_audit_degraded()
        if has_app_context():
            current_app.logger.warning(
                'Bot audit logging degraded for %s:%s',
                target_type,
                target_key,
                exc_info=True,
            )


@bp.after_request
def _apply_bot_audit_status(response):
    audit_status = request.environ.get(
        _BOT_AUDIT_STATUS_ENV_KEY) if has_request_context() else None
    if audit_status:
        response.headers[BOT_AUDIT_STATUS_HEADER] = str(audit_status)
    return response


def _read_env(*keys: str) -> str:
    for key in keys:
        value = str(current_app.config.get(key)
                    or os.getenv(key) or '').strip()
        if value:
            return value
    return ''


def _oauth_config() -> dict[str, str]:
    return {
        'client_id': _read_env(
            'BOT_OPS_DISCORD_CLIENT_ID',
            'OMO_DISCORD_CLIENT_ID',
            'DISCORD_CLIENT_ID',
        ),
        'client_secret': _read_env(
            'BOT_OPS_DISCORD_CLIENT_SECRET',
            'OMO_DISCORD_CLIENT_SECRET',
            'DISCORD_CLIENT_SECRET',
        ),
        'redirect_uri': _read_env(
            'BOT_OPS_DISCORD_REDIRECT_URI',
            'OMO_DISCORD_REDIRECT_URI',
            'DISCORD_REDIRECT_URI',
        ),
    }


def _oauth_ready() -> bool:
    oauth = _oauth_config()
    return all(oauth.values())


def _sanitize_next_url(next_url: object) -> str:
    candidate = str(next_url or '').strip()
    if candidate.startswith('/') and not candidate.startswith('//'):
        return candidate
    return url_for('bot.overview')


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


def operator_session_expired() -> bool:
    last_seen_at = _parse_session_timestamp(
        session.get(BOT_OPS_LAST_SEEN_AT_KEY))
    if last_seen_at is None:
        return True
    return _utcnow() - last_seen_at > _session_idle_timeout()


def refresh_operator_session_activity() -> None:
    session[BOT_OPS_LAST_SEEN_AT_KEY] = _utcnow().isoformat()


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
            **_discord_request_headers(),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        method='POST',
    )
    try:
        with urlopen(token_request, timeout=10) as response:
            token_payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        detail = _decode_http_error(exc)
        if detail:
            raise OperatorAuthError(
                f'Discord OAuth token exchange failed with HTTP {exc.code}: {detail}'
            ) from exc
        raise OperatorAuthError(
            f'Discord OAuth token exchange failed with HTTP {exc.code}.'
        ) from exc
    except URLError as exc:
        raise OperatorAuthError(
            'Discord OAuth token exchange failed because Discord could not be reached.'
        ) from exc

    access_token = str(token_payload.get('access_token', '')).strip()
    if not access_token:
        raise OperatorAuthError(
            'Discord OAuth token exchange did not return an access token.')

    identity_request = Request(
        DISCORD_ME_URL,
        headers=_discord_request_headers(access_token=access_token),
        method='GET',
    )
    try:
        with urlopen(identity_request, timeout=10) as response:
            identity_payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        detail = _decode_http_error(exc)
        if detail:
            raise OperatorAuthError(
                f'Discord OAuth identity lookup failed with HTTP {exc.code}: {detail}'
            ) from exc
        raise OperatorAuthError(
            f'Discord OAuth identity lookup failed with HTTP {exc.code}.'
        ) from exc
    except URLError as exc:
        raise OperatorAuthError(
            'Discord OAuth identity lookup failed because Discord could not be reached.'
        ) from exc

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


def _operator_can(*required_scopes: str) -> bool:
    return bot_operator_service.has_operator_scope(
        session.get(BOT_OPS_SCOPES_SESSION_KEY, []),
        *required_scopes,
    )


def _request_data() -> dict[str, object]:
    if request.is_json:
        return cast(dict[str, object], request.get_json(silent=True) or {})
    return {key: value for key, value in request.form.items()}


def _parse_binding_key(raw_value: object, field_name: str = 'binding_key') -> str:
    binding_key = str(raw_value or '').strip()
    if not binding_key:
        raise ConfigError(f'{field_name} is required.')
    return binding_key


def _parse_required_text(raw_value: object, field_name: str) -> str:
    value = str(raw_value or '').strip()
    if not value:
        raise ConfigError(f'{field_name} is required.')
    return value


def _parse_required_int(raw_value: object, field_name: str) -> int:
    text = str(raw_value or '').strip()
    if not text:
        raise ConfigError(f'{field_name} is required.')
    try:
        return int(text)
    except ValueError as exc:
        raise ConfigError(f'{field_name} must be an integer.') from exc


def _page_syndication_scope_error() -> Any:
    return redirect(url_for('bot.syndication_page', error='operator-scope-required'))


def _page_syndication_config_error() -> Any:
    return redirect(url_for('bot.syndication_page', error='invalid-syndication-config'))


def _page_config_scope_error() -> Any:
    return redirect(url_for('bot.config_page', error='operator-scope-required'))


def _page_config_error() -> Any:
    return redirect(url_for('bot.config_page', error='invalid-syndication-config'))


def _page_config_binding_error() -> Any:
    return redirect(url_for('bot.config_page', error='invalid-config-binding'))


def _page_commands_scope_error() -> Any:
    return redirect(url_for('bot.commands_page', error='operator-scope-required'))


def _page_commands_error() -> Any:
    return redirect(url_for('bot.commands_page', error='invalid-syndication-config'))


def _queue_page_redirect(queue_id: str | None = None, **params: str) -> Any:
    if queue_id:
        return redirect(url_for('bot.queue_detail_page', queue_id=queue_id, **params))
    return redirect(url_for('bot.queues_page', **params))


def _page_queue_scope_error(queue_id: str | None = None) -> Any:
    return _queue_page_redirect(queue_id, error='operator-scope-required')


def _page_queue_config_error(queue_id: str | None = None) -> Any:
    return _queue_page_redirect(queue_id, error='invalid-queue-config')


def _page_queue_action_error(queue_id: str | None = None) -> Any:
    return _queue_page_redirect(queue_id, error='invalid-queue-action')


def _page_queue_not_found_error(queue_id: str | None = None) -> Any:
    return _queue_page_redirect(queue_id, error='queue-not-found')


def _page_queue_confirmation_error(queue_id: str | None = None) -> Any:
    return _queue_page_redirect(queue_id, error='queue-clear-confirmation-required')


def _mileage_page_redirect(user_id: str | None = None, **params: str) -> Any:
    if user_id:
        return redirect(url_for('bot.mileage_detail_page', user_id=user_id, **params))
    return redirect(url_for('bot.mileage_page', **params))


def _page_mileage_scope_error(user_id: str | None = None) -> Any:
    return _mileage_page_redirect(user_id, error='operator-scope-required')


def _page_mileage_config_error(user_id: str | None = None) -> Any:
    return _mileage_page_redirect(user_id, error='invalid-mileage-config')


def _page_mileage_action_error(user_id: str | None = None) -> Any:
    return _mileage_page_redirect(user_id, error='invalid-mileage-action')


def _page_mileage_not_found_error(user_id: str | None = None) -> Any:
    return _mileage_page_redirect(user_id, error='mileage-not-found')


def _load_bot_runtime_settings() -> BotRuntimeSettings:
    return read_runtime_settings()


def _build_queue_service_from_settings(settings: BotRuntimeSettings) -> QueueService:
    if not settings.database_url:
        raise ConfigError(
            'Queue operations require a configured database-backed repository.'
        )
    return QueueService(build_postgres_queue_repository(settings.database_url))


def _serialize_queue_summary(summary: QueueSummary, *, can_write: bool) -> dict[str, object]:
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


def _serialize_queue_entry(entry: QueueEntry, *, can_write: bool) -> dict[str, object]:
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


def _serialize_queue_event(event: QueueEvent) -> dict[str, object]:
    return {
        'event_id': event.event_id,
        'queue_id': event.queue_id,
        'event_type': event.event_type,
        'actor_user_id': event.actor_user_id,
        'entry_id': event.entry_id,
        'payload': cast(dict[str, object], _serialize_audit_value(event.payload)),
        'created_at': event.created_at.isoformat(),
    }


def _serialize_queue_snapshot(snapshot: QueueSnapshot, *, can_write: bool) -> dict[str, object]:
    return {
        'summary': _serialize_queue_summary(snapshot.summary, can_write=can_write),
        'entries': [
            _serialize_queue_entry(entry, can_write=can_write)
            for entry in snapshot.entries
        ],
        'last_event': _serialize_queue_event(snapshot.last_event) if snapshot.last_event else None,
    }


def _serialize_mileage_total(total: MileageTotal, *, can_write: bool) -> dict[str, object]:
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


def _serialize_mileage_event(event: MileageEvent, *, can_write: bool) -> dict[str, object]:
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
        'metadata': cast(dict[str, object], _serialize_audit_value(event.metadata)),
        'created_at': event.created_at.isoformat(),
        'reverse_api': url_for('bot.reverse_mileage_event_api', event_id=event.event_id),
        'reverse_page': url_for('bot.reverse_mileage_event_page_action', event_id=event.event_id),
        'reversible': bool(can_write and event.reversed_event_id is None and event.event_type != 'manual_reversal'),
    }


def _serialize_mileage_tier_stat(tier_stat: MileageTierStat) -> dict[str, object]:
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


def _serialize_mileage_user_detail(detail: MileageUserDetail, *, can_write: bool) -> dict[str, object]:
    return {
        'total': _serialize_mileage_total(detail.total, can_write=can_write),
        'current_tier': _serialize_mileage_tier_stat(MileageTierStat(detail.current_tier, 0)) if detail.current_tier else None,
        'events': [
            _serialize_mileage_event(event, can_write=can_write)
            for event in detail.events
        ],
    }


def _build_mileage_service_from_settings(settings: BotRuntimeSettings) -> MileageService:
    if not settings.database_url:
        raise ConfigError(
            'Mileage operations require a configured database-backed repository.'
        )
    return MileageService(build_postgres_mileage_repository(settings.database_url))


def build_mileage_index_snapshot(*, search: str = '', tier_id: str | None = None) -> dict[str, object]:
    generated_at = _utcnow().isoformat()
    can_write = _operator_can('mileage.write')
    try:
        settings = _load_bot_runtime_settings()
        guild_id = _mileage_active_guild_id(settings)
        service = _build_mileage_service_from_settings(settings)
        tier_stats = service.list_tier_stats(guild_id)
        user_totals = service.list_user_summaries(
            guild_id, search=search, tier_id=tier_id)
        return {
            'status': 'ok',
            'generated_at': generated_at,
            'guild_id': guild_id,
            'search': search,
            'selected_tier_id': tier_id,
            'tiers': [_serialize_mileage_tier_stat(tier_stat) for tier_stat in tier_stats],
            'users': [_serialize_mileage_total(total, can_write=can_write) for total in user_totals],
            'permissions': {'operator_can_write': can_write},
            'repository_error': None,
        }
    except ConfigError as exc:
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
    settings = _load_bot_runtime_settings()
    guild_id = _mileage_active_guild_id(settings)
    service = _build_mileage_service_from_settings(settings)
    detail = service.get_user_detail(guild_id, user_id, limit=50)
    can_write = _operator_can('mileage.write')
    return {
        'status': 'ok',
        'generated_at': _utcnow().isoformat(),
        'guild_id': guild_id,
        'user': _serialize_mileage_user_detail(detail, can_write=can_write),
        'permissions': {'operator_can_write': can_write},
    }


def _mileage_user_before_state(service: MileageService, guild_id: int, user_id: str) -> dict[str, object] | None:
    try:
        detail = service.get_user_detail(guild_id, user_id, limit=50)
    except MileageNotFoundError:
        return None
    return _serialize_mileage_user_detail(detail, can_write=_operator_can('mileage.write'))


def _adjust_mileage_user(user_id: str, display_name: str, delta: int, reason: str, correlation_id: str | None) -> tuple[dict[str, object], dict[str, object]]:
    settings = _load_bot_runtime_settings()
    guild_id = _mileage_active_guild_id(settings)
    service = _build_mileage_service_from_settings(settings)
    before_state = _mileage_user_before_state(service, guild_id, user_id)
    detail, event = service.adjust_user_mileage(
        guild_id=guild_id,
        discord_user_id=user_id,
        display_name=display_name,
        points_delta=delta,
        reason=reason,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
        correlation_id=correlation_id,
    )
    after_state = _serialize_mileage_user_detail(
        detail, can_write=_operator_can('mileage.write'))
    event_payload = _serialize_mileage_event(
        event, can_write=_operator_can('mileage.write'))
    _record_bot_audit_event(
        action_key='mileage.adjusted',
        target_type='mileage_user',
        target_key=user_id,
        before_state=before_state,
        after_state={'user': after_state, 'event': event_payload},
    )
    return after_state, event_payload


def _reverse_mileage_event(event_id: str, reason: str) -> tuple[dict[str, object], dict[str, object]]:
    settings = _load_bot_runtime_settings()
    guild_id = _mileage_active_guild_id(settings)
    service = _build_mileage_service_from_settings(settings)
    original_event = service._repository.get_event(event_id)
    if original_event is None or original_event.guild_id != guild_id:
        raise MileageNotFoundError(f"Mileage event '{event_id}' was not found")
    before_state = _mileage_user_before_state(
        service, guild_id, original_event.discord_user_id)
    detail, reversal_event = service.reverse_event(
        guild_id=guild_id,
        event_id=event_id,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
        reason=reason,
    )
    after_state = _serialize_mileage_user_detail(
        detail, can_write=_operator_can('mileage.write'))
    event_payload = _serialize_mileage_event(
        reversal_event, can_write=_operator_can('mileage.write'))
    _record_bot_audit_event(
        action_key='mileage.reversed',
        target_type='mileage_event',
        target_key=event_id,
        before_state=before_state,
        after_state={'user': after_state, 'event': event_payload},
    )
    return after_state, event_payload


def build_queue_index_snapshot() -> dict[str, object]:
    generated_at = _utcnow().isoformat()
    can_write = _operator_can('queue.write')
    try:
        settings = _load_bot_runtime_settings()
    except ConfigError as exc:
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
        summaries = _build_queue_service_from_settings(settings).list_queues()
        return {
            'status': 'ok',
            'generated_at': generated_at,
            'queues': [_serialize_queue_summary(summary, can_write=can_write) for summary in summaries],
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
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    queue_snapshot = queue_service.get_queue(queue_id)
    queue_events = queue_service.list_events(queue_id, limit=20)
    can_write = _operator_can('queue.write')
    return {
        'status': 'ok',
        'generated_at': _utcnow().isoformat(),
        'queue': _serialize_queue_snapshot(queue_snapshot, can_write=can_write),
        'events': [_serialize_queue_event(event) for event in queue_events],
        'permissions': {'operator_can_write': can_write},
    }


def _queue_before_state(queue_service: QueueService, queue_id: str) -> dict[str, object] | None:
    try:
        snapshot = queue_service.get_queue(queue_id)
    except QueueNotFoundError:
        return None
    return _serialize_queue_snapshot(snapshot, can_write=_operator_can('queue.write'))


def _create_queue(queue_id: str, guild_id: int, label: str) -> dict[str, object]:
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    before_state = _queue_before_state(queue_service, queue_id)
    snapshot = queue_service.ensure_queue(
        queue_id=queue_id, guild_id=guild_id, label=label)
    after_state = _serialize_queue_snapshot(
        snapshot, can_write=_operator_can('queue.write'))
    _record_bot_audit_event(
        action_key='queue.created' if before_state is None else 'queue.updated',
        target_type='queue',
        target_key=queue_id,
        before_state=before_state,
        after_state=after_state,
    )
    return after_state


def _advance_queue(queue_id: str) -> tuple[dict[str, object], dict[str, object]]:
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    before_state = _queue_before_state(queue_service, queue_id)
    snapshot, event = queue_service.advance_queue(
        queue_id=queue_id,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
    )
    after_state = _serialize_queue_snapshot(
        snapshot, can_write=_operator_can('queue.write'))
    event_payload = _serialize_queue_event(event)
    _record_bot_audit_event(
        action_key='queue.advanced',
        target_type='queue',
        target_key=queue_id,
        before_state=before_state,
        after_state={'queue': after_state, 'event': event_payload},
    )
    return after_state, event_payload


def _remove_queue_entry(queue_id: str, entry_id: str, reason: str) -> tuple[dict[str, object], dict[str, object]]:
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    before_state = _queue_before_state(queue_service, queue_id)
    snapshot, event = queue_service.remove_entry(
        queue_id=queue_id,
        entry_id=entry_id,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
        reason=reason,
    )
    after_state = _serialize_queue_snapshot(
        snapshot, can_write=_operator_can('queue.write'))
    event_payload = _serialize_queue_event(event)
    _record_bot_audit_event(
        action_key='queue.entry.removed',
        target_type='queue_entry',
        target_key=entry_id,
        before_state=before_state,
        after_state={'queue': after_state, 'event': event_payload},
    )
    return after_state, event_payload


def _move_queue_entry(queue_id: str, entry_id: str, target_position: int, reason: str) -> tuple[dict[str, object], dict[str, object]]:
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    before_state = _queue_before_state(queue_service, queue_id)
    snapshot, event = queue_service.move_entry(
        queue_id=queue_id,
        entry_id=entry_id,
        target_position=target_position,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
        reason=reason,
    )
    after_state = _serialize_queue_snapshot(
        snapshot, can_write=_operator_can('queue.write'))
    event_payload = _serialize_queue_event(event)
    _record_bot_audit_event(
        action_key='queue.entry.moved',
        target_type='queue_entry',
        target_key=entry_id,
        before_state=before_state,
        after_state={'queue': after_state, 'event': event_payload},
    )
    return after_state, event_payload


def _pause_queue(queue_id: str, reason: str) -> tuple[dict[str, object], dict[str, object]]:
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    before_state = _queue_before_state(queue_service, queue_id)
    snapshot, event = queue_service.pause_queue(
        queue_id=queue_id,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
        reason=reason,
    )
    after_state = _serialize_queue_snapshot(
        snapshot, can_write=_operator_can('queue.write'))
    event_payload = _serialize_queue_event(event)
    _record_bot_audit_event(
        action_key='queue.paused',
        target_type='queue',
        target_key=queue_id,
        before_state=before_state,
        after_state={'queue': after_state, 'event': event_payload},
    )
    return after_state, event_payload


def _resume_queue(queue_id: str) -> tuple[dict[str, object], dict[str, object]]:
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    before_state = _queue_before_state(queue_service, queue_id)
    snapshot, event = queue_service.resume_queue(
        queue_id=queue_id,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
    )
    after_state = _serialize_queue_snapshot(
        snapshot, can_write=_operator_can('queue.write'))
    event_payload = _serialize_queue_event(event)
    _record_bot_audit_event(
        action_key='queue.resumed',
        target_type='queue',
        target_key=queue_id,
        before_state=before_state,
        after_state={'queue': after_state, 'event': event_payload},
    )
    return after_state, event_payload


def _clear_queue(queue_id: str, reason: str, confirmation: str, dry_run: bool = False) -> tuple[dict[str, object], dict[str, object]]:
    if not dry_run and confirmation.strip().lower() != 'clear':
        raise QueueValidationError('Queue clear requires confirm=clear.')
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    before_state = _queue_before_state(queue_service, queue_id)
    snapshot, event = queue_service.clear_queue(
        queue_id=queue_id,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
        reason=reason,
        dry_run=dry_run,
    )
    after_state = _serialize_queue_snapshot(
        snapshot, can_write=_operator_can('queue.write'))
    event_payload = _serialize_queue_event(event)
    if not dry_run:
        _record_bot_audit_event(
            action_key='queue.cleared',
            target_type='queue',
            target_key=queue_id,
            before_state=before_state,
            after_state={'queue': after_state, 'event': event_payload},
        )
    return after_state, event_payload


def _set_active_guild_id(guild_id: int) -> dict[str, object]:
    settings = _load_bot_runtime_settings()
    repository = _build_bot_config_repository_from_settings(settings)
    before_guild_id = repository.get_active_guild_id()
    repository.set_active_guild_id(guild_id)
    guild_config = cast(
        dict[str, object], build_bot_configuration_snapshot()['guild_config'])
    _record_bot_audit_event(
        action_key='config.guild.set',
        target_type='guild_config',
        target_key=str(guild_id),
        before_state={'guild_id': before_guild_id},
        after_state=guild_config,
    )
    return guild_config


def _upsert_channel_binding(binding_key: str, channel_id: int) -> dict[str, object]:
    settings = _effective_runtime_settings(_load_bot_runtime_settings())[0]
    if settings.guild_id is None:
        raise ConfigError(
            'An active guild id is required before channel bindings can be managed.')
    repository = _build_bot_config_repository_from_settings(settings)
    before_binding = next(
        (binding for binding in repository.list_channel_bindings(
            settings.guild_id) if binding['binding_key'] == binding_key),
        None,
    )
    repository.upsert_channel_binding(
        guild_id=settings.guild_id,
        binding_key=binding_key,
        channel_id=channel_id,
    )
    for binding in cast(list[dict[str, object]], build_bot_configuration_snapshot()['channel_bindings']):
        if binding['binding_key'] == binding_key:
            _record_bot_audit_event(
                action_key='config.channel_binding.upserted',
                target_type='channel_binding',
                target_key=binding_key,
                before_state=before_binding,
                after_state=binding,
            )
            return binding
    raise KeyError(binding_key)


def _delete_channel_binding(binding_key: str) -> None:
    settings = _effective_runtime_settings(_load_bot_runtime_settings())[0]
    if settings.guild_id is None:
        raise ConfigError(
            'An active guild id is required before channel bindings can be managed.')
    repository = _build_bot_config_repository_from_settings(settings)
    before_binding = next(
        (binding for binding in repository.list_channel_bindings(
            settings.guild_id) if binding['binding_key'] == binding_key),
        None,
    )
    if not repository.delete_channel_binding(guild_id=settings.guild_id, binding_key=binding_key):
        raise KeyError(binding_key)
    _record_bot_audit_event(
        action_key='config.channel_binding.deleted',
        target_type='channel_binding',
        target_key=binding_key,
        before_state=before_binding,
        after_state=None,
    )


def _upsert_role_binding(binding_key: str, role_id: int) -> dict[str, object]:
    settings = _effective_runtime_settings(_load_bot_runtime_settings())[0]
    if settings.guild_id is None:
        raise ConfigError(
            'An active guild id is required before role bindings can be managed.')
    repository = _build_bot_config_repository_from_settings(settings)
    before_binding = next(
        (binding for binding in repository.list_role_bindings(
            settings.guild_id) if binding['binding_key'] == binding_key),
        None,
    )
    repository.upsert_role_binding(
        guild_id=settings.guild_id,
        binding_key=binding_key,
        role_id=role_id,
    )
    for binding in cast(list[dict[str, object]], build_bot_configuration_snapshot()['role_bindings']):
        if binding['binding_key'] == binding_key:
            _record_bot_audit_event(
                action_key='config.role_binding.upserted',
                target_type='role_binding',
                target_key=binding_key,
                before_state=before_binding,
                after_state=binding,
            )
            return binding
    raise KeyError(binding_key)


def _delete_role_binding(binding_key: str) -> None:
    settings = _effective_runtime_settings(_load_bot_runtime_settings())[0]
    if settings.guild_id is None:
        raise ConfigError(
            'An active guild id is required before role bindings can be managed.')
    repository = _build_bot_config_repository_from_settings(settings)
    before_binding = next(
        (binding for binding in repository.list_role_bindings(
            settings.guild_id) if binding['binding_key'] == binding_key),
        None,
    )
    if not repository.delete_role_binding(guild_id=settings.guild_id, binding_key=binding_key):
        raise KeyError(binding_key)
    _record_bot_audit_event(
        action_key='config.role_binding.deleted',
        target_type='role_binding',
        target_key=binding_key,
        before_state=before_binding,
        after_state=None,
    )


def _run_manual_syndication_retry(source_key: str) -> tuple[dict[str, object], dict[str, object]]:
    settings = _load_bot_runtime_settings()
    if not _configured_syndication_source(settings, source_key):
        raise KeyError(source_key)

    repository = _build_syndication_repository_from_settings(settings)
    before_state = repository.get_by_source_key(
        source_key) or _default_syndication_state(source_key)
    polling_job = _build_manual_syndication_polling_job(settings, repository)
    result = polling_job.run_source_key(source_key, now=_utcnow())
    refreshed_state = repository.get_by_source_key(
        source_key) or _default_syndication_state(source_key)
    _record_bot_audit_event(
        action_key='syndication.source.retried',
        target_type='syndication_source',
        target_key=source_key,
        before_state=before_state,
        after_state=refreshed_state,
    )
    return (
        _serialize_syndication_state(
            refreshed_state,
            now=_utcnow(),
            poll_interval_seconds=settings.syndication_poll_seconds,
            can_write=_operator_can('syndication.write'),
            manual_actions_supported=_manual_syndication_actions_supported(
                settings),
        ),
        {
            'source_key': source_key,
            'delivered_items': result.delivered_items,
            'polled_sources': list(result.polled_sources),
        },
    )


def _reset_syndication_checkpoint(source_key: str) -> dict[str, object]:
    settings = _load_bot_runtime_settings()
    if not _configured_syndication_source(settings, source_key):
        raise KeyError(source_key)

    repository = _build_syndication_repository_from_settings(settings)
    state = repository.get_by_source_key(
        source_key) or _default_syndication_state(source_key)
    reset_state = SyndicationSourceState(
        source_key=state.source_key,
        enabled=state.enabled,
        checkpoint=None,
        last_polled_at=state.last_polled_at,
        last_succeeded_at=state.last_succeeded_at,
        last_failed_at=state.last_failed_at,
    )
    repository.save(reset_state)
    _record_bot_audit_event(
        action_key='syndication.checkpoint.reset',
        target_type='syndication_source',
        target_key=source_key,
        before_state=state,
        after_state=reset_state,
    )
    return _serialize_syndication_state(
        reset_state,
        now=_utcnow(),
        poll_interval_seconds=settings.syndication_poll_seconds,
        can_write=_operator_can('syndication.write'),
        manual_actions_supported=_manual_syndication_actions_supported(
            settings),
    )


def _set_syndication_source_enabled(source_key: str, enabled: bool) -> dict[str, object]:
    settings = _load_bot_runtime_settings()
    if not _configured_syndication_source(settings, source_key):
        raise KeyError(source_key)

    repository = _build_syndication_repository_from_settings(settings)
    state = repository.get_by_source_key(
        source_key) or _default_syndication_state(source_key)
    updated_state = SyndicationSourceState(
        source_key=state.source_key,
        enabled=enabled,
        checkpoint=state.checkpoint,
        last_polled_at=state.last_polled_at,
        last_succeeded_at=state.last_succeeded_at,
        last_failed_at=state.last_failed_at,
    )
    repository.save(updated_state)
    _record_bot_audit_event(
        action_key='syndication.source.enabled' if enabled else 'syndication.source.disabled',
        target_type='syndication_source',
        target_key=source_key,
        before_state=state,
        after_state=updated_state,
    )
    return _serialize_syndication_state(
        updated_state,
        now=_utcnow(),
        poll_interval_seconds=settings.syndication_poll_seconds,
        can_write=_operator_can('syndication.write'),
        manual_actions_supported=_manual_syndication_actions_supported(
            settings),
    )


def _login_redirect_response(expired: bool = False):
    if request.path.startswith('/bot/api/'):
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
            'bot.login',
            next=request.url,
            error='session-expired' if expired else None,
        )
    )


def _operator_scope_denied_response(*required_scopes: str):
    if request.path.startswith('/bot/api/'):
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


bp.before_request(require_operator_session)
bp.add_url_rule('/login', view_func=login, methods=['GET'])
bp.add_url_rule('/oauth/start', view_func=oauth_start, methods=['GET'])
bp.add_url_rule('/oauth/callback', view_func=oauth_callback, methods=['GET'])
bp.add_url_rule('/logout', view_func=logout, methods=['POST'])


bp.add_url_rule('', view_func=overview, methods=['GET'])
bp.add_url_rule('/', view_func=overview, methods=['GET'])
bp.add_url_rule(
    '/health', view_func=health_page, methods=['GET'])
bp.add_url_rule(
    '/api/health', view_func=health_api, methods=['GET'])
bp.add_url_rule(
    '/api/health/services', view_func=health_services_api, methods=['GET'])
bp.add_url_rule(
    '/api/health/jobs', view_func=health_jobs_api, methods=['GET'])
bp.add_url_rule('/operators', view_func=operators_page, methods=['GET'])
bp.add_url_rule('/api/operators', view_func=operators_api, methods=['GET'])
bp.add_url_rule('/api/operators/<user_id>/disable',
                view_func=disable_operator_api, methods=['POST'])
bp.add_url_rule('/operators/<user_id>/disable',
                view_func=disable_operator_page_action, methods=['POST'])
bp.add_url_rule('/api/operators/<user_id>/enable',
                view_func=enable_operator_api, methods=['POST'])
bp.add_url_rule('/operators/<user_id>/enable',
                view_func=enable_operator_page_action, methods=['POST'])
bp.add_url_rule('/api/operators/<user_id>/scopes',
                view_func=update_operator_scopes_api, methods=['POST'])
bp.add_url_rule('/operators/<user_id>/scopes',
                view_func=update_operator_scopes_page_action, methods=['POST'])
bp.add_url_rule('/queues', view_func=queues_page, methods=['GET'])
bp.add_url_rule('/queues/<path:queue_id>',
                view_func=queue_detail_page, methods=['GET'])
bp.add_url_rule('/api/queues', view_func=queues_api, methods=['GET'])
bp.add_url_rule('/api/queues/<path:queue_id>',
                view_func=queue_detail_api, methods=['GET'])
bp.add_url_rule('/api/queues/<path:queue_id>/events',
                view_func=queue_events_api, methods=['GET'])
bp.add_url_rule('/api/queues', view_func=create_queue_api, methods=['POST'])
bp.add_url_rule('/queues', view_func=create_queue_page_action,
                methods=['POST'])
bp.add_url_rule('/api/queues/<path:queue_id>/advance',
                view_func=advance_queue_api, methods=['POST'])
bp.add_url_rule('/queues/<path:queue_id>/advance',
                view_func=advance_queue_page_action, methods=['POST'])
bp.add_url_rule('/api/queues/<path:queue_id>/entries/<entry_id>/remove',
                view_func=remove_queue_entry_api, methods=['POST'])
bp.add_url_rule('/queues/<path:queue_id>/entries/<entry_id>/remove',
                view_func=remove_queue_entry_page_action, methods=['POST'])
bp.add_url_rule('/api/queues/<path:queue_id>/entries/<entry_id>/move',
                view_func=move_queue_entry_api, methods=['POST'])
bp.add_url_rule('/queues/<path:queue_id>/entries/<entry_id>/move',
                view_func=move_queue_entry_page_action, methods=['POST'])
bp.add_url_rule('/api/queues/<path:queue_id>/pause',
                view_func=pause_queue_api, methods=['POST'])
bp.add_url_rule('/queues/<path:queue_id>/pause',
                view_func=pause_queue_page_action, methods=['POST'])
bp.add_url_rule('/api/queues/<path:queue_id>/resume',
                view_func=resume_queue_api, methods=['POST'])
bp.add_url_rule('/queues/<path:queue_id>/resume',
                view_func=resume_queue_page_action, methods=['POST'])
bp.add_url_rule('/api/queues/<path:queue_id>/clear',
                view_func=clear_queue_api, methods=['POST'])
bp.add_url_rule('/queues/<path:queue_id>/clear',
                view_func=clear_queue_page_action, methods=['POST'])
bp.add_url_rule('/mileage', view_func=mileage_page, methods=['GET'])
bp.add_url_rule('/mileage/<user_id>',
                view_func=mileage_detail_page, methods=['GET'])
bp.add_url_rule('/api/mileage/users',
                view_func=mileage_users_api, methods=['GET'])
bp.add_url_rule('/api/mileage/users/<user_id>',
                view_func=mileage_user_detail_api, methods=['GET'])
bp.add_url_rule('/api/mileage/users/<user_id>/events',
                view_func=mileage_user_events_api, methods=['GET'])
bp.add_url_rule('/api/mileage/tiers',
                view_func=mileage_tiers_api, methods=['GET'])
bp.add_url_rule('/api/mileage/users/<user_id>/adjust',
                view_func=adjust_mileage_user_api, methods=['POST'])
bp.add_url_rule('/mileage/users/<user_id>/adjust',
                view_func=adjust_mileage_user_page_action, methods=['POST'])
bp.add_url_rule('/api/mileage/events/<event_id>/reverse',
                view_func=reverse_mileage_event_api, methods=['POST'])
bp.add_url_rule('/mileage/events/<event_id>/reverse',
                view_func=reverse_mileage_event_page_action, methods=['POST'])
bp.add_url_rule('/config', view_func=config_page, methods=['GET'])
bp.add_url_rule('/api/config', view_func=config_api, methods=['GET'])
bp.add_url_rule('/api/config/guild',
                view_func=set_active_guild_api, methods=['POST'])
bp.add_url_rule('/config/guild',
                view_func=set_active_guild_page_action, methods=['POST'])
bp.add_url_rule('/api/config/channels',
                view_func=upsert_channel_binding_api, methods=['POST'])
bp.add_url_rule('/config/channels',
                view_func=upsert_channel_binding_page_action, methods=['POST'])
bp.add_url_rule('/api/config/channels/<binding_key>/delete',
                view_func=delete_channel_binding_api, methods=['POST'])
bp.add_url_rule('/config/channels/<binding_key>/delete',
                view_func=delete_channel_binding_page_action, methods=['POST'])
bp.add_url_rule('/api/config/roles',
                view_func=upsert_role_binding_api, methods=['POST'])
bp.add_url_rule('/config/roles',
                view_func=upsert_role_binding_page_action, methods=['POST'])
bp.add_url_rule('/api/config/roles/<binding_key>/delete',
                view_func=delete_role_binding_api, methods=['POST'])
bp.add_url_rule('/config/roles/<binding_key>/delete',
                view_func=delete_role_binding_page_action, methods=['POST'])
bp.add_url_rule('/api/config/sources/<source_key>/enable',
                view_func=enable_syndication_source_api, methods=['POST'])
bp.add_url_rule('/config/sources/<source_key>/enable',
                view_func=enable_syndication_source_page_action, methods=['POST'])
bp.add_url_rule('/api/config/sources/<source_key>/disable',
                view_func=disable_syndication_source_api, methods=['POST'])
bp.add_url_rule('/config/sources/<source_key>/disable',
                view_func=disable_syndication_source_page_action, methods=['POST'])
bp.add_url_rule('/syndication', view_func=syndication_page, methods=['GET'])
bp.add_url_rule('/api/syndication', view_func=syndication_api, methods=['GET'])
bp.add_url_rule('/api/syndication/sources',
                view_func=syndication_sources_api, methods=['GET'])
bp.add_url_rule('/api/syndication/channels',
                view_func=syndication_channels_api, methods=['GET'])
bp.add_url_rule('/api/syndication/sources/<source_key>/retry',
                view_func=retry_syndication_source_api, methods=['POST'])
bp.add_url_rule('/syndication/sources/<source_key>/retry',
                view_func=retry_syndication_source_page_action, methods=['POST'])
bp.add_url_rule('/api/syndication/sources/<source_key>/checkpoint/reset',
                view_func=reset_syndication_checkpoint_api, methods=['POST'])
bp.add_url_rule('/syndication/sources/<source_key>/checkpoint/reset',
                view_func=reset_syndication_checkpoint_page_action, methods=['POST'])
bp.add_url_rule('/commands', view_func=commands_page, methods=['GET'])
bp.add_url_rule('/api/commands', view_func=commands_api, methods=['GET'])
bp.add_url_rule('/api/commands/poll-all',
                view_func=poll_all_sources_api, methods=['POST'])
bp.add_url_rule('/commands/poll-all',
                view_func=poll_all_sources_page_action, methods=['POST'])
bp.add_url_rule('/onboarding', view_func=onboarding_page, methods=['GET'])
bp.add_url_rule('/onboarding/events',
                view_func=list_onboarding_events_api, methods=['GET'])
bp.add_url_rule('/onboarding/replay',
                view_func=replay_onboarding_api, methods=['POST'])
bp.add_url_rule('/onboarding/reset',
                view_func=reset_onboarding_api, methods=['POST'])
bp.add_url_rule('/onboarding/role-cleanup',
                view_func=request_onboarding_role_cleanup_api, methods=['POST'])
bp.add_url_rule('/api/diagnostics', view_func=diagnostics_api, methods=['GET'])


@bp.get('/moderation')
def moderation_page():
    return render_template(
        'moderation.html',
        error=request.args.get('error'),
    )


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

def _build_onboarding_service() -> 'OnboardingService | None':
    if not BOT_MODULE_AVAILABLE or build_postgres_onboarding_repository is None or OnboardingService is None:
        return None
    try:
        settings = _load_bot_runtime_settings()
        if not settings.database_url:
            return None
        return OnboardingService(
            onboarding_repository=build_postgres_onboarding_repository(
                settings.database_url)
        )
    except Exception:
        return None
