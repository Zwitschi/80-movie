from __future__ import annotations

import logging
from typing import cast

from flask import current_app, url_for

logger = logging.getLogger(__name__)


def _build_bot_config_repository_from_settings(settings):
    from . import admin_bot

    if not settings.database_url:
        raise admin_bot.ConfigError(
            'Bot configuration management requires a configured database-backed repository.'
        )
    return admin_bot.build_postgres_bot_config_repository(settings.database_url)


def _effective_runtime_settings(settings):
    from . import admin_bot

    if not settings.database_url:
        logger.info("No database_url — using env-backed runtime settings")
        return settings, None, False

    try:
        managed = _build_bot_config_repository_from_settings(settings).load_runtime_config(
            default_guild_id=settings.guild_id,
            default_channel_map=settings.channel_map,
            default_role_map=settings.role_map,
        )
        logger.info("Loaded managed runtime config: guild=%s channels=%d roles=%d",
                     managed.guild_id, len(managed.channel_map), len(managed.role_map))
        return (
            admin_bot.BotRuntimeSettings(
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
        logger.warning("Failed to load managed runtime config: %s", exc)
        return settings, str(exc), False


def _config_write_supported(settings) -> bool:
    from . import admin_bot

    return bool(settings.database_url and admin_bot._operator_can('syndication.write'))


def _build_syndication_repository_from_settings(settings):
    from . import admin_bot

    if not settings.database_url:
        raise admin_bot.ConfigError(
            'Manual syndication actions require a configured database-backed repository.'
        )
    return admin_bot.build_postgres_syndication_repository(settings.database_url)


def _build_manual_syndication_polling_job(settings, repository):
    from . import admin_bot

    config = admin_bot._build_bot_config_from_runtime_settings(settings)
    return admin_bot.SyndicationPollingJob(
        planning_service=admin_bot.SyndicationPlanningService(
            config=config,
            repository=repository,
        ),
        repository=repository,
        adapters=admin_bot.build_syndication_adapters(config),
        delivery_sink=admin_bot.NullSyndicationDeliverySink(),
    )


def _serialize_syndication_state(
    state,
    *,
    now,
    poll_interval_seconds: int,
    can_write: bool,
    manual_actions_supported: bool,
):
    from . import admin_bot

    due_now = state.is_due(
        now=now, poll_interval_seconds=poll_interval_seconds)
    last_poll_result = admin_bot._syndication_last_poll_result(state)
    return {
        'source_key': state.source_key,
        'enabled': state.enabled,
        'checkpoint': state.checkpoint,
        'last_polled_at': state.last_polled_at.isoformat() if state.last_polled_at else None,
        'last_succeeded_at': state.last_succeeded_at.isoformat() if state.last_succeeded_at else None,
        'last_failed_at': state.last_failed_at.isoformat() if state.last_failed_at else None,
        'due_now': due_now,
        'last_poll_result': last_poll_result,
        'status': admin_bot._syndication_source_status(state, due_now=due_now),
        'actions': {
            'can_write': can_write,
            'manual_actions_supported': manual_actions_supported,
            'retry_api': url_for('bot.retry_syndication_source_api', source_key=state.source_key),
            'reset_checkpoint_api': url_for('bot.reset_syndication_checkpoint_api', source_key=state.source_key),
            'retry_page': url_for('bot.retry_syndication_source_page_action', source_key=state.source_key),
            'reset_checkpoint_page': url_for('bot.reset_syndication_checkpoint_page_action', source_key=state.source_key),
        },
    }


def build_discord_guild_snapshot(guild_id: int | None) -> dict[str, object]:
    """Fetch guild metadata, channels, roles, and members from Discord API."""
    from .bot_utils import _fetch_discord_guild, _fetch_discord_channels, _fetch_discord_roles, _fetch_discord_members

    if not guild_id:
        return {
            'available': False,
            'guild': None,
            'channels': [],
            'roles': [],
            'members': [],
            'error': 'no_guild_id_configured',
        }

    guild = _fetch_discord_guild(guild_id)
    if guild is None:
        return {
            'available': False,
            'guild': None,
            'channels': [],
            'roles': [],
            'members': [],
            'error': 'discord_api_unavailable',
        }

    channels = _fetch_discord_channels(guild_id)
    roles = _fetch_discord_roles(guild_id)
    members = _fetch_discord_members(guild_id)

    return {
        'available': True,
        'guild': guild,
        'channels': channels,
        'roles': roles,
        'members': members,
        'error': None,
    }


def build_syndication_snapshot() -> dict[str, object]:
    from . import admin_bot

    now = admin_bot._utcnow()

    try:
        settings = _effective_runtime_settings(
            admin_bot._load_bot_runtime_settings())[0]
    except admin_bot.ConfigError as exc:
        return {
            'status': 'invalid_config',
            'generated_at': now.isoformat(),
            'error': str(exc),
            'bot_runtime': {
                'discord_token_configured': bool(admin_bot._read_env('OMO_DISCORD_TOKEN', 'DISCORD_TOKEN')),
                'database_configured': bool(current_app.config.get('DATABASE_URL')),
            },
            'sources': [],
            'channel_bindings': [],
        }

    repository_backend = 'in-memory'
    repository_error = None
    source_states: list[dict[str, object]] = []
    can_write = admin_bot._operator_can('syndication.write')
    manual_actions_supported = admin_bot._manual_syndication_actions_supported(
        settings)

    if settings.database_url:
        repository_backend = 'postgresql'
        try:
            repository = admin_bot.build_postgres_syndication_repository(
                settings.database_url)
            for source_key in settings.syndication_sources:
                state = repository.get_by_source_key(
                    source_key) or admin_bot._default_syndication_state(source_key)
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
                    admin_bot._default_syndication_state(source_key),
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
        'summary': admin_bot._syndication_summary(source_states),
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
                'managed_by': 'repository' if bot_runtime['manual_actions_supported'] else 'runtime-default',
                'editable': bool(bot_runtime['manual_actions_supported'] and bot_runtime['operator_can_write']),
                'enable_api': url_for('bot.enable_syndication_source_api', source_key=source['source_key']),
                'disable_api': url_for('bot.disable_syndication_source_api', source_key=source['source_key']),
                'enable_page': url_for('bot.enable_syndication_source_page_action', source_key=source['source_key']),
                'disable_page': url_for('bot.disable_syndication_source_page_action', source_key=source['source_key']),
            }
            for source in cast(list[dict[str, object]], syndication['sources'])
        ],
        'channel_bindings': [
            {
                'binding_key': binding_key,
                'channel_id': channel_id,
                'managed_by': 'repository' if managed_by_repository else 'environment',
                'editable': bool(managed_by_repository and _config_write_supported(effective_settings)),
                'delete_api': url_for('bot.delete_channel_binding_api', binding_key=binding_key),
                'delete_page': url_for('bot.delete_channel_binding_page_action', binding_key=binding_key),
            }
            for binding_key, channel_id in sorted(effective_settings.channel_map.items())
        ],
        'role_bindings': [
            {
                'binding_key': binding_key,
                'role_id': role_id,
                'managed_by': 'repository' if managed_by_repository else 'runtime-default',
                'editable': bool(managed_by_repository and _config_write_supported(effective_settings)),
                'delete_api': url_for('bot.delete_role_binding_api', binding_key=binding_key),
                'delete_page': url_for('bot.delete_role_binding_page_action', binding_key=binding_key),
            }
            for binding_key, role_id in sorted(effective_settings.role_map.items())
        ],
        'guild_config': {
            'guild_id': effective_settings.guild_id,
            'managed_by': 'repository' if managed_by_repository else 'environment',
            'editable': bool(managed_by_repository and _config_write_supported(effective_settings)),
            'set_api': url_for('bot.set_active_guild_api'),
            'set_page': url_for('bot.set_active_guild_page_action'),
        },
        'bot_runtime': bot_runtime,
        'discord_guild': build_discord_guild_snapshot(effective_settings.guild_id),
        'permissions': {
            'can_manage_sources': bool(bot_runtime['manual_actions_supported'] and bot_runtime['operator_can_write']),
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
                'api_url': url_for('bot.poll_all_sources_api'),
                'page_url': url_for('bot.poll_all_sources_page_action'),
            },
        ],
        'sources': config_snapshot['sources'],
        'channel_bindings': config_snapshot['channel_bindings'],
        'role_bindings': config_snapshot['role_bindings'],
        'permissions': config_snapshot['permissions'],
    }


def _run_manual_syndication_poll_all() -> dict[str, object]:
    from . import admin_bot

    settings = admin_bot._load_bot_runtime_settings()
    repository = _build_syndication_repository_from_settings(settings)
    polling_job = _build_manual_syndication_polling_job(settings, repository)
    total_delivered_items = 0
    source_results: list[dict[str, object]] = []

    for source_key in settings.syndication_sources:
        result = polling_job.run_source_key(
            source_key, now=admin_bot._utcnow())
        total_delivered_items += result.delivered_items
        state = repository.get_by_source_key(
            source_key) or admin_bot._default_syndication_state(source_key)
        source_results.append(
            _serialize_syndication_state(
                state,
                now=admin_bot._utcnow(),
                poll_interval_seconds=settings.syndication_poll_seconds,
                can_write=admin_bot._operator_can('syndication.write'),
                manual_actions_supported=admin_bot._manual_syndication_actions_supported(
                    settings),
            )
        )

    result = {
        'source_count': len(settings.syndication_sources),
        'delivered_items': total_delivered_items,
        'sources': source_results,
    }
    admin_bot._record_bot_audit_event(
        action_key='syndication.sources.polled_all',
        target_type='syndication_batch',
        target_key='all_sources',
        before_state={'source_keys': list(settings.syndication_sources)},
        after_state=result,
    )
    return result


def _load_bot_runtime_settings():
    from . import admin_bot

    return admin_bot._load_bot_runtime_settings()
