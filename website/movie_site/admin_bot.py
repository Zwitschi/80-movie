from __future__ import annotations

import json
import os
from secrets import token_urlsafe
from datetime import datetime, timedelta, timezone
from typing import Any, cast
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
    from bot.omo_bot.models import MileageEvent, MileageTierStat, MileageTotal, MileageUserDetail, QueueEntry, QueueEvent, QueueSnapshot, QueueSummary, SyndicationSourceState
    from bot.omo_bot.repositories import (
        build_postgres_bot_audit_log_repository,
        build_postgres_bot_config_repository,
        build_postgres_mileage_repository,
        build_postgres_queue_repository,
        build_postgres_syndication_repository,
    )
    from bot.omo_bot.services import BotAuditService, NullSyndicationDeliverySink, SyndicationPlanningService
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
    build_postgres_queue_repository = None  # type: ignore[misc,assignment]
    # type: ignore[misc,assignment]
    build_postgres_syndication_repository = None
    BotAuditService = None  # type: ignore[misc,assignment]
    NullSyndicationDeliverySink = None  # type: ignore[misc,assignment]
    SyndicationPlanningService = None  # type: ignore[misc,assignment]
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


admin_bot_blueprint = Blueprint('admin_bot', __name__, url_prefix='/admin/bot')

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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_audit_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _serialize_audit_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_audit_value(item) for item in value]
    return value


def _serialize_audit_state(state: object) -> dict[str, object] | None:
    if state is None:
        return None
    if isinstance(state, dict):
        return cast(dict[str, object], _serialize_audit_value(state))
    if hasattr(state, '__dict__'):
        return cast(dict[str, object], _serialize_audit_value(vars(state)))
    return {'value': cast(object, _serialize_audit_value(state))}


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


@admin_bot_blueprint.after_request
def add_bot_audit_status_header(response):
    audit_status = str(request.environ.get(
        _BOT_AUDIT_STATUS_ENV_KEY, '')).strip()
    if audit_status:
        response.headers[BOT_AUDIT_STATUS_HEADER] = audit_status
    return response


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


def _default_syndication_state(source_key: str) -> SyndicationSourceState:
    return SyndicationSourceState(source_key=source_key)


def _operator_can(*required_scopes: str) -> bool:
    return bot_operator_service.has_operator_scope(
        session.get(BOT_OPS_SCOPES_SESSION_KEY, []),
        *required_scopes,
    )


def _manual_syndication_actions_supported(settings: BotRuntimeSettings) -> bool:
    return bool(settings.database_url)


def _syndication_last_poll_result(state: SyndicationSourceState) -> str:
    if state.last_failed_at and (
        state.last_succeeded_at is None or state.last_failed_at >= state.last_succeeded_at
    ):
        return 'failed'
    if state.last_succeeded_at:
        return 'succeeded'
    if state.last_polled_at:
        return 'in_progress'
    return 'never'


def _syndication_source_status(
    state: SyndicationSourceState,
    *,
    due_now: bool,
) -> str:
    if not state.enabled:
        return 'disabled'
    if _syndication_last_poll_result(state) == 'failed':
        return 'attention'
    if due_now:
        return 'due'
    if state.last_succeeded_at:
        return 'healthy'
    return 'idle'


def _syndication_summary(source_states: list[dict[str, object]]) -> dict[str, int]:
    return {
        'source_count': len(source_states),
        'due_source_count': sum(1 for source in source_states if source['status'] == 'due'),
        'attention_source_count': sum(
            1 for source in source_states if source['status'] == 'attention'
        ),
    }


def _build_bot_config_from_runtime_settings(settings: BotRuntimeSettings) -> BotConfig:
    return BotConfig(
        discord_token=settings.discord_token or 'control-room-placeholder-token',
        guild_id=settings.guild_id,
        channel_map=settings.channel_map,
        database_url=settings.database_url,
        syndication_sources=settings.syndication_sources,
        syndication_poll_seconds=settings.syndication_poll_seconds,
        role_map=settings.role_map,
        log_level=settings.log_level,
    )


def _build_bot_config_repository_from_settings(settings: BotRuntimeSettings):
    if not settings.database_url:
        raise ConfigError(
            'Bot configuration management requires a configured database-backed repository.'
        )
    return build_postgres_bot_config_repository(settings.database_url)


def _effective_runtime_settings(
    settings: BotRuntimeSettings,
) -> tuple[BotRuntimeSettings, str | None, bool]:
    if not settings.database_url:
        return settings, None, False

    try:
        managed = _build_bot_config_repository_from_settings(settings).load_runtime_config(
            default_guild_id=settings.guild_id,
            default_channel_map=settings.channel_map,
            default_role_map=settings.role_map,
        )
        return (
            BotRuntimeSettings(
                discord_token=settings.discord_token,
                guild_id=managed.guild_id,
                channel_map=managed.channel_map,
                database_url=settings.database_url,
                syndication_sources=settings.syndication_sources,
                syndication_poll_seconds=settings.syndication_poll_seconds,
                role_map=managed.role_map,
                log_level=settings.log_level,
            ),
            None,
            managed.managed_by_repository,
        )
    except Exception as exc:
        return settings, str(exc), False


def _config_write_supported(settings: BotRuntimeSettings) -> bool:
    return bool(settings.database_url and _operator_can('syndication.write'))


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


def _build_syndication_repository_from_settings(settings: BotRuntimeSettings):
    if not settings.database_url:
        raise ConfigError(
            'Manual syndication actions require a configured database-backed repository.'
        )
    return build_postgres_syndication_repository(settings.database_url)


def _build_manual_syndication_polling_job(
    settings: BotRuntimeSettings,
    repository,
) -> SyndicationPollingJob:
    config = _build_bot_config_from_runtime_settings(settings)
    return SyndicationPollingJob(
        planning_service=SyndicationPlanningService(
            config=config,
            repository=repository,
        ),
        repository=repository,
        adapters=build_syndication_adapters(config),
        delivery_sink=NullSyndicationDeliverySink(),
    )


def _configured_syndication_source(settings: BotRuntimeSettings, source_key: str) -> bool:
    return source_key in settings.syndication_sources


def _page_syndication_scope_error() -> Any:
    return redirect(url_for('admin_bot.syndication_page', error='operator-scope-required'))


def _page_syndication_config_error() -> Any:
    return redirect(url_for('admin_bot.syndication_page', error='invalid-syndication-config'))


def _page_config_scope_error() -> Any:
    return redirect(url_for('admin_bot.config_page', error='operator-scope-required'))


def _page_config_error() -> Any:
    return redirect(url_for('admin_bot.config_page', error='invalid-syndication-config'))


def _page_config_binding_error() -> Any:
    return redirect(url_for('admin_bot.config_page', error='invalid-config-binding'))


def _page_commands_scope_error() -> Any:
    return redirect(url_for('admin_bot.commands_page', error='operator-scope-required'))


def _page_commands_error() -> Any:
    return redirect(url_for('admin_bot.commands_page', error='invalid-syndication-config'))


def _queue_page_redirect(queue_id: str | None = None, **params: str) -> Any:
    if queue_id:
        return redirect(url_for('admin_bot.queue_detail_page', queue_id=queue_id, **params))
    return redirect(url_for('admin_bot.queues_page', **params))


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
        return redirect(url_for('admin_bot.mileage_detail_page', user_id=user_id, **params))
    return redirect(url_for('admin_bot.mileage_page', **params))


def _page_mileage_scope_error(user_id: str | None = None) -> Any:
    return _mileage_page_redirect(user_id, error='operator-scope-required')


def _page_mileage_config_error(user_id: str | None = None) -> Any:
    return _mileage_page_redirect(user_id, error='invalid-mileage-config')


def _page_mileage_action_error(user_id: str | None = None) -> Any:
    return _mileage_page_redirect(user_id, error='invalid-mileage-action')


def _page_mileage_not_found_error(user_id: str | None = None) -> Any:
    return _mileage_page_redirect(user_id, error='mileage-not-found')


def _serialize_syndication_state(
    state: SyndicationSourceState,
    *,
    now: datetime,
    poll_interval_seconds: int,
    can_write: bool,
    manual_actions_supported: bool,
) -> dict[str, object]:
    due_now = state.is_due(
        now=now, poll_interval_seconds=poll_interval_seconds)
    last_poll_result = _syndication_last_poll_result(state)
    return {
        'source_key': state.source_key,
        'enabled': state.enabled,
        'checkpoint': state.checkpoint,
        'last_polled_at': state.last_polled_at.isoformat() if state.last_polled_at else None,
        'last_succeeded_at': state.last_succeeded_at.isoformat() if state.last_succeeded_at else None,
        'last_failed_at': state.last_failed_at.isoformat() if state.last_failed_at else None,
        'due_now': due_now,
        'last_poll_result': last_poll_result,
        'status': _syndication_source_status(state, due_now=due_now),
        'actions': {
            'can_write': can_write,
            'manual_actions_supported': manual_actions_supported,
            'retry_api': url_for('admin_bot.retry_syndication_source_api', source_key=state.source_key),
            'reset_checkpoint_api': url_for(
                'admin_bot.reset_syndication_checkpoint_api', source_key=state.source_key
            ),
            'retry_page': url_for('admin_bot.retry_syndication_source_page_action', source_key=state.source_key),
            'reset_checkpoint_page': url_for(
                'admin_bot.reset_syndication_checkpoint_page_action', source_key=state.source_key
            ),
        },
    }


def _load_bot_runtime_settings() -> BotRuntimeSettings:
    return read_runtime_settings()


def build_syndication_snapshot() -> dict[str, object]:
    now = _utcnow()

    try:
        settings = _effective_runtime_settings(_load_bot_runtime_settings())[0]
    except ConfigError as exc:
        return {
            'status': 'invalid_config',
            'generated_at': now.isoformat(),
            'error': str(exc),
            'bot_runtime': {
                'discord_token_configured': bool(_read_env('OMO_DISCORD_TOKEN', 'DISCORD_TOKEN')),
                'database_configured': bool(current_app.config.get('DATABASE_URL')),
            },
            'sources': [],
            'channel_bindings': [],
        }

    repository_backend = 'in-memory'
    repository_error = None
    source_states: list[dict[str, object]] = []
    can_write = _operator_can('syndication.write')
    manual_actions_supported = _manual_syndication_actions_supported(settings)

    if settings.database_url:
        repository_backend = 'postgresql'
        try:
            repository = build_postgres_syndication_repository(
                settings.database_url)
            for source_key in settings.syndication_sources:
                state = repository.get_by_source_key(
                    source_key) or _default_syndication_state(source_key)
                source_states.append(
                    _serialize_syndication_state(
                        state,
                        now=now,
                        poll_interval_seconds=settings.syndication_poll_seconds,
                        can_write=can_write,
                        manual_actions_supported=manual_actions_supported,
                    )
                )
        except Exception as exc:
            repository_error = str(exc)

    if not source_states:
        for source_key in settings.syndication_sources:
            source_states.append(
                _serialize_syndication_state(
                    _default_syndication_state(source_key),
                    now=now,
                    poll_interval_seconds=settings.syndication_poll_seconds,
                    can_write=can_write,
                    manual_actions_supported=manual_actions_supported,
                )
            )

    channel_bindings = [
        {'binding_key': binding_key, 'channel_id': channel_id}
        for binding_key, channel_id in sorted(settings.channel_map.items())
    ]

    status = 'degraded' if repository_error else 'ok'
    return {
        'status': status,
        'generated_at': now.isoformat(),
        'bot_runtime': {
            'discord_token_configured': bool(settings.discord_token),
            'guild_id': settings.guild_id,
            'database_configured': bool(settings.database_url),
            'syndication_poll_seconds': settings.syndication_poll_seconds,
            'log_level': settings.log_level,
            'repository_backend': repository_backend,
            'repository_error': repository_error,
            'manual_actions_supported': manual_actions_supported,
            'operator_can_write': can_write,
        },
        'summary': _syndication_summary(source_states),
        'sources': source_states,
        'channel_bindings': channel_bindings,
    }


def build_bot_configuration_snapshot() -> dict[str, object]:
    raw_settings = _load_bot_runtime_settings()
    effective_settings, config_repository_error, managed_by_repository = _effective_runtime_settings(
        raw_settings)
    syndication = build_syndication_snapshot()
    bot_runtime = cast(dict[str, object], syndication['bot_runtime'])
    return {
        'status': 'degraded' if config_repository_error else syndication['status'],
        'generated_at': syndication['generated_at'],
        'sources': [
            {
                **source,
                'managed_by': (
                    'repository' if bot_runtime['manual_actions_supported'] else 'runtime-default'
                ),
                'editable': bool(
                    bot_runtime['manual_actions_supported']
                    and bot_runtime['operator_can_write']
                ),
                'enable_api': url_for('admin_bot.enable_syndication_source_api', source_key=source['source_key']),
                'disable_api': url_for('admin_bot.disable_syndication_source_api', source_key=source['source_key']),
                'enable_page': url_for('admin_bot.enable_syndication_source_page_action', source_key=source['source_key']),
                'disable_page': url_for('admin_bot.disable_syndication_source_page_action', source_key=source['source_key']),
            }
            for source in cast(list[dict[str, object]], syndication['sources'])
        ],
        'channel_bindings': [
            {
                'binding_key': binding_key,
                'channel_id': channel_id,
                'managed_by': 'repository' if managed_by_repository else 'environment',
                'editable': bool(managed_by_repository and _config_write_supported(effective_settings)),
                'delete_api': url_for('admin_bot.delete_channel_binding_api', binding_key=binding_key),
                'delete_page': url_for('admin_bot.delete_channel_binding_page_action', binding_key=binding_key),
            }
            for binding_key, channel_id in sorted(effective_settings.channel_map.items())
        ],
        'role_bindings': [
            {
                'binding_key': binding_key,
                'role_id': role_id,
                'managed_by': 'repository' if managed_by_repository else 'runtime-default',
                'editable': bool(managed_by_repository and _config_write_supported(effective_settings)),
                'delete_api': url_for('admin_bot.delete_role_binding_api', binding_key=binding_key),
                'delete_page': url_for('admin_bot.delete_role_binding_page_action', binding_key=binding_key),
            }
            for binding_key, role_id in sorted(effective_settings.role_map.items())
        ],
        'guild_config': {
            'guild_id': effective_settings.guild_id,
            'managed_by': 'repository' if managed_by_repository else 'environment',
            'editable': bool(managed_by_repository and _config_write_supported(effective_settings)),
            'set_api': url_for('admin_bot.set_active_guild_api'),
            'set_page': url_for('admin_bot.set_active_guild_page_action'),
        },
        'bot_runtime': bot_runtime,
        'permissions': {
            'can_manage_sources': bool(
                bot_runtime['manual_actions_supported']
                and bot_runtime['operator_can_write']
            ),
            'can_manage_channel_bindings': bool(managed_by_repository and _config_write_supported(effective_settings)),
            'can_manage_role_bindings': bool(managed_by_repository and _config_write_supported(effective_settings)),
            'can_manage_guild_config': bool(managed_by_repository and _config_write_supported(effective_settings)),
            'operator_can_write': bot_runtime['operator_can_write'],
        },
        'repository_error': config_repository_error,
    }


def build_bot_commands_snapshot() -> dict[str, object]:
    config_snapshot = build_bot_configuration_snapshot()
    bot_runtime = cast(dict[str, object], config_snapshot['bot_runtime'])
    return {
        'status': config_snapshot['status'],
        'generated_at': config_snapshot['generated_at'],
        'available_commands': [
            {
                'command_key': 'poll_all_sources',
                'label': 'Poll all sources now',
                'required_scope': 'syndication.write',
                'supported': bool(bot_runtime['manual_actions_supported']),
                'api_url': url_for('admin_bot.poll_all_sources_api'),
                'page_url': url_for('admin_bot.poll_all_sources_page_action'),
            },
        ],
        'sources': config_snapshot['sources'],
        'channel_bindings': config_snapshot['channel_bindings'],
        'role_bindings': config_snapshot['role_bindings'],
        'permissions': config_snapshot['permissions'],
    }


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
        'detail_api': url_for('admin_bot.queue_detail_api', queue_id=summary.queue_id),
        'detail_page': url_for('admin_bot.queue_detail_page', queue_id=summary.queue_id),
        'events_api': url_for('admin_bot.queue_events_api', queue_id=summary.queue_id),
        'advance_api': url_for('admin_bot.advance_queue_api', queue_id=summary.queue_id),
        'advance_page': url_for('admin_bot.advance_queue_page_action', queue_id=summary.queue_id),
        'pause_api': url_for('admin_bot.pause_queue_api', queue_id=summary.queue_id),
        'pause_page': url_for('admin_bot.pause_queue_page_action', queue_id=summary.queue_id),
        'resume_api': url_for('admin_bot.resume_queue_api', queue_id=summary.queue_id),
        'resume_page': url_for('admin_bot.resume_queue_page_action', queue_id=summary.queue_id),
        'clear_api': url_for('admin_bot.clear_queue_api', queue_id=summary.queue_id),
        'clear_page': url_for('admin_bot.clear_queue_page_action', queue_id=summary.queue_id),
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
        'remove_api': url_for('admin_bot.remove_queue_entry_api', queue_id=entry.queue_id, entry_id=entry.entry_id),
        'remove_page': url_for('admin_bot.remove_queue_entry_page_action', queue_id=entry.queue_id, entry_id=entry.entry_id),
        'move_api': url_for('admin_bot.move_queue_entry_api', queue_id=entry.queue_id, entry_id=entry.entry_id),
        'move_page': url_for('admin_bot.move_queue_entry_page_action', queue_id=entry.queue_id, entry_id=entry.entry_id),
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


def _build_mileage_service_from_settings(settings: BotRuntimeSettings) -> MileageService:
    if not settings.database_url:
        raise ConfigError(
            'Mileage operations require a configured database-backed repository.'
        )
    return MileageService(build_postgres_mileage_repository(settings.database_url))


def _mileage_active_guild_id(settings: BotRuntimeSettings) -> int:
    if settings.guild_id is None:
        raise ConfigError(
            'An active guild id is required for mileage operations.')
    return settings.guild_id


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
        'detail_api': url_for('admin_bot.mileage_user_detail_api', user_id=total.discord_user_id),
        'detail_page': url_for('admin_bot.mileage_detail_page', user_id=total.discord_user_id),
        'adjust_api': url_for('admin_bot.adjust_mileage_user_api', user_id=total.discord_user_id),
        'adjust_page': url_for('admin_bot.adjust_mileage_user_page_action', user_id=total.discord_user_id),
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
        'reverse_api': url_for('admin_bot.reverse_mileage_event_api', event_id=event.event_id),
        'reverse_page': url_for('admin_bot.reverse_mileage_event_page_action', event_id=event.event_id),
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
            'create_api': url_for('admin_bot.create_queue_api'),
            'create_page': url_for('admin_bot.create_queue_page_action'),
        }

    if not settings.database_url:
        return {
            'status': 'missing_config',
            'generated_at': generated_at,
            'queues': [],
            'permissions': {'operator_can_write': can_write},
            'repository_error': 'Queue operations require a configured database-backed repository.',
            'create_api': url_for('admin_bot.create_queue_api'),
            'create_page': url_for('admin_bot.create_queue_page_action'),
        }

    try:
        summaries = _build_queue_service_from_settings(settings).list_queues()
        return {
            'status': 'ok',
            'generated_at': generated_at,
            'queues': [_serialize_queue_summary(summary, can_write=can_write) for summary in summaries],
            'permissions': {'operator_can_write': can_write},
            'repository_error': None,
            'create_api': url_for('admin_bot.create_queue_api'),
            'create_page': url_for('admin_bot.create_queue_page_action'),
        }
    except Exception as exc:
        return {
            'status': 'error',
            'generated_at': generated_at,
            'queues': [],
            'permissions': {'operator_can_write': can_write},
            'repository_error': str(exc),
            'create_api': url_for('admin_bot.create_queue_api'),
            'create_page': url_for('admin_bot.create_queue_page_action'),
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


def _clear_queue(queue_id: str, reason: str, confirmation: str) -> tuple[dict[str, object], dict[str, object]]:
    if confirmation.strip().lower() != 'clear':
        raise QueueValidationError('Queue clear requires confirm=clear.')
    settings = _load_bot_runtime_settings()
    queue_service = _build_queue_service_from_settings(settings)
    before_state = _queue_before_state(queue_service, queue_id)
    snapshot, event = queue_service.clear_queue(
        queue_id=queue_id,
        actor_user_id=str(session.get(
            BOT_OPS_SESSION_KEY, '')).strip() or None,
        reason=reason,
    )
    after_state = _serialize_queue_snapshot(
        snapshot, can_write=_operator_can('queue.write'))
    event_payload = _serialize_queue_event(event)
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


def _run_manual_syndication_poll_all() -> dict[str, object]:
    settings = _load_bot_runtime_settings()
    repository = _build_syndication_repository_from_settings(settings)
    polling_job = _build_manual_syndication_polling_job(settings, repository)
    total_delivered_items = 0
    source_results: list[dict[str, object]] = []

    for source_key in settings.syndication_sources:
        result = polling_job.run_source_key(source_key, now=_utcnow())
        total_delivered_items += result.delivered_items
        state = repository.get_by_source_key(
            source_key) or _default_syndication_state(source_key)
        source_results.append(
            _serialize_syndication_state(
                state,
                now=_utcnow(),
                poll_interval_seconds=settings.syndication_poll_seconds,
                can_write=_operator_can('syndication.write'),
                manual_actions_supported=_manual_syndication_actions_supported(
                    settings),
            )
        )

    result = {
        'source_count': len(settings.syndication_sources),
        'delivered_items': total_delivered_items,
        'sources': source_results,
    }
    _record_bot_audit_event(
        action_key='syndication.sources.polled_all',
        target_type='syndication_batch',
        target_key='all_sources',
        before_state={'source_keys': list(settings.syndication_sources)},
        after_state=result,
    )
    return result


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

    before_state = bot_operator_repo.get_bot_operator_by_discord_user_id(
        user_id)
    operator_record = bot_operator_repo.set_bot_operator_active(
        user_id, is_active)
    if operator_record is None:
        return _operator_not_found_response()
    _record_bot_audit_event(
        action_key='operator.enabled' if is_active else 'operator.disabled',
        target_type='operator',
        target_key=user_id,
        before_state=before_state,
        after_state=operator_record,
    )
    return operator_record


def _update_operator_scopes(user_id: str, raw_scopes: object):
    scope_error = require_operator_scope('operators.write')
    if scope_error is not None:
        return scope_error

    before_state = bot_operator_repo.get_bot_operator_by_discord_user_id(
        user_id)
    scopes = bot_operator_service.normalize_operator_scopes(raw_scopes)
    if not scopes:
        return _invalid_operator_scopes_response()

    operator_record = bot_operator_repo.set_bot_operator_scopes(
        user_id, scopes)
    if operator_record is None:
        return _operator_not_found_response()
    _record_bot_audit_event(
        action_key='operator.scopes.updated',
        target_type='operator',
        target_key=user_id,
        before_state=before_state,
        after_state=operator_record,
    )
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
    return render_template('admin/bot/health.html', health=health, syndication=build_syndication_snapshot())


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


@admin_bot_blueprint.get('/syndication')
def syndication_page():
    return render_template(
        'admin/bot/syndication.html',
        syndication=build_syndication_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


@admin_bot_blueprint.get('/config')
def config_page():
    return render_template(
        'admin/bot/config.html',
        config_snapshot=build_bot_configuration_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


@admin_bot_blueprint.get('/commands')
def commands_page():
    return render_template(
        'admin/bot/commands.html',
        commands_snapshot=build_bot_commands_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


@admin_bot_blueprint.get('/mileage')
def mileage_page():
    return render_template(
        'admin/bot/mileage.html',
        mileage_snapshot=build_mileage_index_snapshot(
            search=str(request.args.get('q') or '').strip(),
            tier_id=str(request.args.get('tier_id') or '').strip() or None,
        ),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


@admin_bot_blueprint.get('/mileage/<user_id>')
def mileage_detail_page(user_id: str):
    try:
        mileage_detail_snapshot = build_mileage_detail_snapshot(user_id)
    except ConfigError:
        return _page_mileage_config_error(user_id)
    except MileageNotFoundError:
        return _page_mileage_not_found_error()

    return render_template(
        'admin/bot/mileage_detail.html',
        mileage_detail_snapshot=mileage_detail_snapshot,
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


@admin_bot_blueprint.get('/queues')
def queues_page():
    return render_template(
        'admin/bot/queues.html',
        queue_index_snapshot=build_queue_index_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


@admin_bot_blueprint.get('/queues/<path:queue_id>')
def queue_detail_page(queue_id: str):
    try:
        queue_detail_snapshot = build_queue_detail_snapshot(queue_id)
    except ConfigError:
        return _page_queue_config_error(queue_id)
    except QueueNotFoundError:
        return _page_queue_not_found_error()

    return render_template(
        'admin/bot/queue_detail.html',
        queue_detail_snapshot=queue_detail_snapshot,
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


@admin_bot_blueprint.get('/api/operators')
def operators_api():
    return jsonify({'data': bot_operator_repo.list_bot_operators()})


@admin_bot_blueprint.get('/api/syndication')
def syndication_api():
    return jsonify({'data': build_syndication_snapshot()})


@admin_bot_blueprint.get('/api/config')
def config_api():
    return jsonify({'data': build_bot_configuration_snapshot()})


@admin_bot_blueprint.post('/api/config/guild')
def set_active_guild_api():
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    payload = _request_data()
    try:
        guild = _set_active_guild_id(_parse_required_int(
            payload.get('guild_id'), 'guild_id'))
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409

    return jsonify({'data': guild})


@admin_bot_blueprint.post('/config/guild')
def set_active_guild_page_action():
    if not _operator_can('syndication.write'):
        return _page_config_scope_error()

    try:
        _set_active_guild_id(_parse_required_int(
            request.form.get('guild_id'), 'guild_id'))
    except ConfigError:
        return _page_config_binding_error()

    return redirect(url_for('admin_bot.config_page', saved='guild-updated'))


@admin_bot_blueprint.post('/api/config/channels')
def upsert_channel_binding_api():
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    payload = _request_data()
    try:
        binding = _upsert_channel_binding(
            _parse_binding_key(payload.get('binding_key')),
            _parse_required_int(payload.get('channel_id'), 'channel_id'),
        )
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409

    return jsonify({'data': binding})


@admin_bot_blueprint.post('/config/channels')
def upsert_channel_binding_page_action():
    if not _operator_can('syndication.write'):
        return _page_config_scope_error()

    try:
        _upsert_channel_binding(
            _parse_binding_key(request.form.get('binding_key')),
            _parse_required_int(request.form.get('channel_id'), 'channel_id'),
        )
    except ConfigError:
        return _page_config_binding_error()

    return redirect(url_for('admin_bot.config_page', saved='channel-binding-saved'))


@admin_bot_blueprint.post('/api/config/channels/<binding_key>/delete')
def delete_channel_binding_api(binding_key: str):
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        _delete_channel_binding(binding_key)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'binding_not_found', 'message': 'Channel binding was not found.'}}), 404

    return jsonify({'data': {'binding_key': binding_key, 'deleted': True}})


@admin_bot_blueprint.post('/config/channels/<binding_key>/delete')
def delete_channel_binding_page_action(binding_key: str):
    if not _operator_can('syndication.write'):
        return _page_config_scope_error()

    try:
        _delete_channel_binding(binding_key)
    except (ConfigError, KeyError):
        return _page_config_binding_error()

    return redirect(url_for('admin_bot.config_page', saved='channel-binding-deleted'))


@admin_bot_blueprint.post('/api/config/roles')
def upsert_role_binding_api():
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    payload = _request_data()
    try:
        binding = _upsert_role_binding(
            _parse_binding_key(payload.get('binding_key')),
            _parse_required_int(payload.get('role_id'), 'role_id'),
        )
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409

    return jsonify({'data': binding})


@admin_bot_blueprint.post('/config/roles')
def upsert_role_binding_page_action():
    if not _operator_can('syndication.write'):
        return _page_config_scope_error()

    try:
        _upsert_role_binding(
            _parse_binding_key(request.form.get('binding_key')),
            _parse_required_int(request.form.get('role_id'), 'role_id'),
        )
    except ConfigError:
        return _page_config_binding_error()

    return redirect(url_for('admin_bot.config_page', saved='role-binding-saved'))


@admin_bot_blueprint.post('/api/config/roles/<binding_key>/delete')
def delete_role_binding_api(binding_key: str):
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        _delete_role_binding(binding_key)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'binding_not_found', 'message': 'Role binding was not found.'}}), 404

    return jsonify({'data': {'binding_key': binding_key, 'deleted': True}})


@admin_bot_blueprint.post('/config/roles/<binding_key>/delete')
def delete_role_binding_page_action(binding_key: str):
    if not _operator_can('syndication.write'):
        return _page_config_scope_error()

    try:
        _delete_role_binding(binding_key)
    except (ConfigError, KeyError):
        return _page_config_binding_error()

    return redirect(url_for('admin_bot.config_page', saved='role-binding-deleted'))


@admin_bot_blueprint.get('/api/commands')
def commands_api():
    return jsonify({'data': build_bot_commands_snapshot()})


@admin_bot_blueprint.get('/api/queues')
def queues_api():
    snapshot = build_queue_index_snapshot()
    return jsonify({'data': snapshot['queues'], 'meta': {'status': snapshot['status'], 'generated_at': snapshot['generated_at']}})


@admin_bot_blueprint.get('/api/queues/<path:queue_id>')
def queue_detail_api(queue_id: str):
    try:
        snapshot = build_queue_detail_snapshot(queue_id)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404

    return jsonify({'data': snapshot['queue'], 'meta': {'events_count': len(snapshot['events']), 'generated_at': snapshot['generated_at']}})


@admin_bot_blueprint.get('/api/queues/<path:queue_id>/events')
def queue_events_api(queue_id: str):
    try:
        snapshot = build_queue_detail_snapshot(queue_id)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404

    return jsonify({'data': snapshot['events'], 'meta': {'generated_at': snapshot['generated_at']}})


@admin_bot_blueprint.get('/api/mileage/users')
def mileage_users_api():
    snapshot = build_mileage_index_snapshot(
        search=str(request.args.get('q') or '').strip(),
        tier_id=str(request.args.get('tier_id') or '').strip() or None,
    )
    return jsonify({'data': snapshot['users'], 'meta': {'status': snapshot['status'], 'generated_at': snapshot['generated_at'], 'guild_id': snapshot['guild_id']}})


@admin_bot_blueprint.get('/api/mileage/users/<user_id>')
def mileage_user_detail_api(user_id: str):
    try:
        snapshot = build_mileage_detail_snapshot(user_id)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_config', 'message': str(exc)}}), 409
    except MileageNotFoundError:
        return jsonify({'error': {'code': 'mileage_not_found', 'message': 'Mileage user was not found.'}}), 404

    return jsonify({'data': snapshot['user'], 'meta': {'generated_at': snapshot['generated_at'], 'guild_id': snapshot['guild_id']}})


@admin_bot_blueprint.get('/api/mileage/users/<user_id>/events')
def mileage_user_events_api(user_id: str):
    try:
        snapshot = build_mileage_detail_snapshot(user_id)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_config', 'message': str(exc)}}), 409
    except MileageNotFoundError:
        return jsonify({'error': {'code': 'mileage_not_found', 'message': 'Mileage user was not found.'}}), 404

    return jsonify({'data': snapshot['user']['events'], 'meta': {'generated_at': snapshot['generated_at'], 'guild_id': snapshot['guild_id']}})


@admin_bot_blueprint.get('/api/mileage/tiers')
def mileage_tiers_api():
    snapshot = build_mileage_index_snapshot(
        search=str(request.args.get('q') or '').strip(),
        tier_id=str(request.args.get('tier_id') or '').strip() or None,
    )
    return jsonify({'data': snapshot['tiers'], 'meta': {'status': snapshot['status'], 'generated_at': snapshot['generated_at'], 'guild_id': snapshot['guild_id']}})


@admin_bot_blueprint.post('/api/mileage/users/<user_id>/adjust')
def adjust_mileage_user_api(user_id: str):
    scope_error = require_operator_scope('mileage.write')
    if scope_error is not None:
        return scope_error

    payload = _request_data()
    try:
        user, event = _adjust_mileage_user(
            user_id,
            _parse_required_text(payload.get('display_name')
                                 or user_id, 'display_name'),
            _parse_required_int(payload.get('delta'), 'delta'),
            _parse_required_text(payload.get('reason'), 'reason'),
            str(payload.get('correlation_id') or '').strip() or None,
        )
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_config', 'message': str(exc)}}), 409
    except MileageValidationError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_action', 'message': str(exc)}}), 400

    return jsonify({'data': user, 'meta': {'event': event}})


@admin_bot_blueprint.post('/mileage/users/<user_id>/adjust')
def adjust_mileage_user_page_action(user_id: str):
    if not _operator_can('mileage.write'):
        return _page_mileage_scope_error(user_id)

    try:
        _adjust_mileage_user(
            user_id,
            _parse_required_text(request.form.get(
                'display_name') or user_id, 'display_name'),
            _parse_required_int(request.form.get('delta'), 'delta'),
            _parse_required_text(request.form.get('reason'), 'reason'),
            str(request.form.get('correlation_id') or '').strip() or None,
        )
    except ConfigError:
        return _page_mileage_config_error(user_id)
    except MileageValidationError:
        return _page_mileage_action_error(user_id)

    return _mileage_page_redirect(user_id, saved='mileage-adjusted')


@admin_bot_blueprint.post('/api/mileage/events/<event_id>/reverse')
def reverse_mileage_event_api(event_id: str):
    scope_error = require_operator_scope('mileage.write')
    if scope_error is not None:
        return scope_error

    payload = _request_data()
    try:
        user, event = _reverse_mileage_event(
            event_id,
            _parse_required_text(payload.get('reason'), 'reason'),
        )
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_config', 'message': str(exc)}}), 409
    except MileageNotFoundError:
        return jsonify({'error': {'code': 'mileage_not_found', 'message': 'Mileage event was not found.'}}), 404
    except (MileageValidationError, MileageConflictError) as exc:
        return jsonify({'error': {'code': 'invalid_mileage_action', 'message': str(exc)}}), 409

    return jsonify({'data': user, 'meta': {'event': event}})


@admin_bot_blueprint.post('/mileage/events/<event_id>/reverse')
def reverse_mileage_event_page_action(event_id: str):
    if not _operator_can('mileage.write'):
        return _page_mileage_scope_error()
    try:
        user, _event = _reverse_mileage_event(
            event_id,
            _parse_required_text(request.form.get('reason'), 'reason'),
        )
    except ConfigError:
        return _page_mileage_config_error()
    except MileageNotFoundError:
        return _page_mileage_not_found_error()
    except (MileageValidationError, MileageConflictError):
        return _page_mileage_action_error()

    return _mileage_page_redirect(str(cast(dict[str, object], user['total'])['discord_user_id']), saved='mileage-reversed')


@admin_bot_blueprint.post('/api/queues')
def create_queue_api():
    scope_error = require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error

    payload = _request_data()
    try:
        queue = _create_queue(
            _parse_required_text(payload.get('queue_id'), 'queue_id'),
            _parse_required_int(payload.get('guild_id'), 'guild_id'),
            _parse_required_text(payload.get('label'), 'label'),
        )
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409

    return jsonify({'data': queue})


@admin_bot_blueprint.post('/queues')
def create_queue_page_action():
    if not _operator_can('queue.write'):
        return _page_queue_scope_error()

    try:
        queue = _create_queue(
            _parse_required_text(request.form.get('queue_id'), 'queue_id'),
            _parse_required_int(request.form.get('guild_id'), 'guild_id'),
            _parse_required_text(request.form.get('label'), 'label'),
        )
    except ConfigError:
        return _page_queue_config_error()

    return _queue_page_redirect(str(cast(dict[str, object], queue['summary'])['queue_id']), saved='queue-created')


@admin_bot_blueprint.post('/api/queues/<path:queue_id>/advance')
def advance_queue_api(queue_id: str):
    scope_error = require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error

    try:
        queue, event = _advance_queue(queue_id)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except (QueuePausedError, QueueConflictError) as exc:
        return jsonify({'error': {'code': 'queue_conflict', 'message': str(exc)}}), 409

    return jsonify({'data': queue, 'meta': {'event': event}})


@admin_bot_blueprint.post('/queues/<path:queue_id>/advance')
def advance_queue_page_action(queue_id: str):
    if not _operator_can('queue.write'):
        return _page_queue_scope_error(queue_id)
    try:
        _advance_queue(queue_id)
    except ConfigError:
        return _page_queue_config_error(queue_id)
    except QueueNotFoundError:
        return _page_queue_not_found_error()
    except (QueuePausedError, QueueConflictError):
        return _page_queue_action_error(queue_id)
    return _queue_page_redirect(queue_id, saved='queue-advanced')


@admin_bot_blueprint.post('/api/queues/<path:queue_id>/entries/<entry_id>/remove')
def remove_queue_entry_api(queue_id: str, entry_id: str):
    scope_error = require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error

    payload = _request_data()
    try:
        queue, event = _remove_queue_entry(
            queue_id, entry_id, str(payload.get('reason') or '').strip())
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except QueueEntryNotFoundError:
        return jsonify({'error': {'code': 'queue_entry_not_found', 'message': 'Queue entry was not found.'}}), 404

    return jsonify({'data': queue, 'meta': {'event': event}})


@admin_bot_blueprint.post('/queues/<path:queue_id>/entries/<entry_id>/remove')
def remove_queue_entry_page_action(queue_id: str, entry_id: str):
    if not _operator_can('queue.write'):
        return _page_queue_scope_error(queue_id)
    try:
        _remove_queue_entry(queue_id, entry_id, str(
            request.form.get('reason') or '').strip())
    except ConfigError:
        return _page_queue_config_error(queue_id)
    except QueueNotFoundError:
        return _page_queue_not_found_error()
    except QueueEntryNotFoundError:
        return _page_queue_action_error(queue_id)
    return _queue_page_redirect(queue_id, saved='entry-removed')


@admin_bot_blueprint.post('/api/queues/<path:queue_id>/entries/<entry_id>/move')
def move_queue_entry_api(queue_id: str, entry_id: str):
    scope_error = require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error

    payload = _request_data()
    try:
        queue, event = _move_queue_entry(
            queue_id,
            entry_id,
            _parse_required_int(payload.get(
                'target_position'), 'target_position'),
            str(payload.get('reason') or '').strip(),
        )
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except QueueEntryNotFoundError:
        return jsonify({'error': {'code': 'queue_entry_not_found', 'message': 'Queue entry was not found.'}}), 404
    except QueueValidationError as exc:
        return jsonify({'error': {'code': 'invalid_queue_action', 'message': str(exc)}}), 400
    except QueuePausedError as exc:
        return jsonify({'error': {'code': 'queue_conflict', 'message': str(exc)}}), 409

    return jsonify({'data': queue, 'meta': {'event': event}})


@admin_bot_blueprint.post('/queues/<path:queue_id>/entries/<entry_id>/move')
def move_queue_entry_page_action(queue_id: str, entry_id: str):
    if not _operator_can('queue.write'):
        return _page_queue_scope_error(queue_id)
    try:
        _move_queue_entry(
            queue_id,
            entry_id,
            _parse_required_int(request.form.get(
                'target_position'), 'target_position'),
            str(request.form.get('reason') or '').strip(),
        )
    except ConfigError:
        return _page_queue_config_error(queue_id)
    except (QueueEntryNotFoundError, QueueValidationError, QueuePausedError):
        return _page_queue_action_error(queue_id)
    except QueueNotFoundError:
        return _page_queue_not_found_error()
    return _queue_page_redirect(queue_id, saved='entry-moved')


@admin_bot_blueprint.post('/api/queues/<path:queue_id>/pause')
def pause_queue_api(queue_id: str):
    scope_error = require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error
    payload = _request_data()
    try:
        queue, event = _pause_queue(queue_id, str(
            payload.get('reason') or '').strip())
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except QueueConflictError as exc:
        return jsonify({'error': {'code': 'queue_conflict', 'message': str(exc)}}), 409

    return jsonify({'data': queue, 'meta': {'event': event}})


@admin_bot_blueprint.post('/queues/<path:queue_id>/pause')
def pause_queue_page_action(queue_id: str):
    if not _operator_can('queue.write'):
        return _page_queue_scope_error(queue_id)
    try:
        _pause_queue(queue_id, str(request.form.get('reason') or '').strip())
    except ConfigError:
        return _page_queue_config_error(queue_id)
    except QueueNotFoundError:
        return _page_queue_not_found_error()
    except QueueConflictError:
        return _page_queue_action_error(queue_id)
    return _queue_page_redirect(queue_id, saved='queue-paused')


@admin_bot_blueprint.post('/api/queues/<path:queue_id>/resume')
def resume_queue_api(queue_id: str):
    scope_error = require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error
    try:
        queue, event = _resume_queue(queue_id)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except QueueConflictError as exc:
        return jsonify({'error': {'code': 'queue_conflict', 'message': str(exc)}}), 409

    return jsonify({'data': queue, 'meta': {'event': event}})


@admin_bot_blueprint.post('/queues/<path:queue_id>/resume')
def resume_queue_page_action(queue_id: str):
    if not _operator_can('queue.write'):
        return _page_queue_scope_error(queue_id)
    try:
        _resume_queue(queue_id)
    except ConfigError:
        return _page_queue_config_error(queue_id)
    except QueueNotFoundError:
        return _page_queue_not_found_error()
    except QueueConflictError:
        return _page_queue_action_error(queue_id)
    return _queue_page_redirect(queue_id, saved='queue-resumed')


@admin_bot_blueprint.post('/api/queues/<path:queue_id>/clear')
def clear_queue_api(queue_id: str):
    scope_error = require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error
    payload = _request_data()
    try:
        queue, event = _clear_queue(
            queue_id,
            str(payload.get('reason') or '').strip(),
            str(payload.get('confirm') or '').strip(),
        )
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except QueueValidationError as exc:
        return jsonify({'error': {'code': 'invalid_queue_action', 'message': str(exc)}}), 400

    return jsonify({'data': queue, 'meta': {'event': event}})


@admin_bot_blueprint.post('/queues/<path:queue_id>/clear')
def clear_queue_page_action(queue_id: str):
    if not _operator_can('queue.write'):
        return _page_queue_scope_error(queue_id)
    try:
        _clear_queue(
            queue_id,
            str(request.form.get('reason') or '').strip(),
            str(request.form.get('confirm') or '').strip(),
        )
    except ConfigError:
        return _page_queue_config_error(queue_id)
    except QueueNotFoundError:
        return _page_queue_not_found_error()
    except QueueValidationError:
        return _page_queue_confirmation_error(queue_id)
    return _queue_page_redirect(queue_id, saved='queue-cleared')


@admin_bot_blueprint.get('/api/syndication/sources')
def syndication_sources_api():
    snapshot = build_syndication_snapshot()
    return jsonify({'data': snapshot['sources'], 'meta': {'status': snapshot['status']}})


@admin_bot_blueprint.get('/api/syndication/channels')
def syndication_channels_api():
    snapshot = build_syndication_snapshot()
    return jsonify({'data': snapshot['channel_bindings'], 'meta': {'status': snapshot['status']}})


@admin_bot_blueprint.post('/api/syndication/sources/<source_key>/retry')
def retry_syndication_source_api(source_key: str):
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        source_state, meta = _run_manual_syndication_retry(source_key)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'syndication_source_not_found', 'message': 'Configured syndication source was not found.'}}), 404
    except Exception as exc:
        return jsonify({'error': {'code': 'syndication_retry_failed', 'message': str(exc)}}), 500

    return jsonify({'data': source_state, 'meta': meta})


@admin_bot_blueprint.post('/syndication/sources/<source_key>/retry')
def retry_syndication_source_page_action(source_key: str):
    if not _operator_can('syndication.write'):
        return _page_syndication_scope_error()

    try:
        _run_manual_syndication_retry(source_key)
    except ConfigError:
        return _page_syndication_config_error()
    except KeyError:
        return redirect(url_for('admin_bot.syndication_page', error='source-not-found'))
    except Exception:
        return redirect(url_for('admin_bot.syndication_page', error='retry-failed'))

    return redirect(url_for('admin_bot.syndication_page', saved='retry'))


@admin_bot_blueprint.post('/api/syndication/sources/<source_key>/checkpoint/reset')
def reset_syndication_checkpoint_api(source_key: str):
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        source_state = _reset_syndication_checkpoint(source_key)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'syndication_source_not_found', 'message': 'Configured syndication source was not found.'}}), 404

    return jsonify({'data': source_state})


@admin_bot_blueprint.post('/syndication/sources/<source_key>/checkpoint/reset')
def reset_syndication_checkpoint_page_action(source_key: str):
    if not _operator_can('syndication.write'):
        return _page_syndication_scope_error()

    try:
        _reset_syndication_checkpoint(source_key)
    except ConfigError:
        return _page_syndication_config_error()
    except KeyError:
        return redirect(url_for('admin_bot.syndication_page', error='source-not-found'))

    return redirect(url_for('admin_bot.syndication_page', saved='checkpoint-reset'))


@admin_bot_blueprint.post('/api/config/sources/<source_key>/enable')
def enable_syndication_source_api(source_key: str):
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        source_state = _set_syndication_source_enabled(source_key, True)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'syndication_source_not_found', 'message': 'Configured syndication source was not found.'}}), 404

    return jsonify({'data': source_state})


@admin_bot_blueprint.post('/config/sources/<source_key>/enable')
def enable_syndication_source_page_action(source_key: str):
    if not _operator_can('syndication.write'):
        return _page_config_scope_error()

    try:
        _set_syndication_source_enabled(source_key, True)
    except ConfigError:
        return _page_config_error()
    except KeyError:
        return redirect(url_for('admin_bot.config_page', error='source-not-found'))

    return redirect(url_for('admin_bot.config_page', saved='source-enabled'))


@admin_bot_blueprint.post('/api/config/sources/<source_key>/disable')
def disable_syndication_source_api(source_key: str):
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        source_state = _set_syndication_source_enabled(source_key, False)
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'syndication_source_not_found', 'message': 'Configured syndication source was not found.'}}), 404

    return jsonify({'data': source_state})


@admin_bot_blueprint.post('/config/sources/<source_key>/disable')
def disable_syndication_source_page_action(source_key: str):
    if not _operator_can('syndication.write'):
        return _page_config_scope_error()

    try:
        _set_syndication_source_enabled(source_key, False)
    except ConfigError:
        return _page_config_error()
    except KeyError:
        return redirect(url_for('admin_bot.config_page', error='source-not-found'))

    return redirect(url_for('admin_bot.config_page', saved='source-disabled'))


@admin_bot_blueprint.post('/api/commands/poll-all')
def poll_all_sources_api():
    scope_error = require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        result = _run_manual_syndication_poll_all()
    except ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except Exception as exc:
        return jsonify({'error': {'code': 'command_failed', 'message': str(exc)}}), 500

    return jsonify({'data': result})


@admin_bot_blueprint.post('/commands/poll-all')
def poll_all_sources_page_action():
    if not _operator_can('syndication.write'):
        return _page_commands_scope_error()

    try:
        _run_manual_syndication_poll_all()
    except ConfigError:
        return _page_commands_error()
    except Exception:
        return redirect(url_for('admin_bot.commands_page', error='command-failed'))

    return redirect(url_for('admin_bot.commands_page', saved='poll-all'))


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
