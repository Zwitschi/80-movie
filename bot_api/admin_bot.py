from __future__ import annotations
from .auth_runtime import (
    _record_bot_audit_event,
    _apply_bot_audit_status,
)
from .queue_mileage_snapshot import (
    _build_queue_service_from_settings,
    _serialize_queue_event,
    _serialize_queue_snapshot,
    _serialize_mileage_event,
    _serialize_mileage_user_detail,
    _build_mileage_service_from_settings,
    _mileage_user_before_state,
    _queue_before_state,
)
from .runtime_snapshot import (
    _build_bot_config_repository_from_settings,
    _effective_runtime_settings,
    _build_syndication_repository_from_settings,
    _build_manual_syndication_polling_job,
    _serialize_syndication_state,
    build_bot_configuration_snapshot,
)
from .onboarding_routes import (
    onboarding_page,
    list_onboarding_events_api,
    replay_onboarding_api,
    reset_onboarding_api,
    request_onboarding_role_cleanup_api,
)
from .diagnostics_routes import diagnostics_api
from .command_routes import (
    commands_page,
    commands_api,
    poll_all_sources_api,
    poll_all_sources_page_action,
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
from .auth_routes import (
    require_operator_session,
    login,
    oauth_start,
    oauth_callback,
    logout,
)
from .health_routes import (
    overview,
    health_page,
    health_api,
    health_services_api,
    health_jobs_api,
)
from .bot_utils import (
    _configured_syndication_source,
    _default_syndication_state,
    _manual_syndication_actions_supported,
    _mileage_active_guild_id,
    _parse_session_timestamp,
    _utcnow,
)
from . import bot_operator_service

from datetime import timedelta
from typing import cast

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

# Bot imports are deferred so the website can start even when deployed
# from the website/ subdirectory (where bot/ is not on the Python path).
# When bot/ is available (repo-root deploy or PYTHONPATH includes root),
# these imports resolve normally.
from bot.omo_bot.config import BotRuntimeSettings, ConfigError, read_runtime_settings
from bot.omo_bot.models import SyndicationSourceState
from bot.omo_bot.services.mileage_service import (
    MileageNotFoundError,
)
from bot.omo_bot.services.queue_service import (
    QueueValidationError,
)
BOT_MODULE_AVAILABLE = True


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


bp.after_request(_apply_bot_audit_status)


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


def _operator_can(*required_scopes: str) -> bool:
    return bot_operator_service.has_operator_scope(
        session.get(BOT_OPS_SCOPES_SESSION_KEY, []),
        *required_scopes,
    )


def _load_bot_runtime_settings() -> BotRuntimeSettings:
    return read_runtime_settings()


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
