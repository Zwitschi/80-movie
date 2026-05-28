from __future__ import annotations

import logging

from flask import jsonify, redirect, render_template, request, url_for

from .bot_utils import _discord_bot_token

logger = logging.getLogger(__name__)


def config_page():
    from . import admin_bot

    return render_template(
        'config.html',
        config_snapshot=admin_bot.build_bot_configuration_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


def guild_page():
    from . import admin_bot

    return render_template(
        'guild.html',
        config_snapshot=admin_bot.build_bot_configuration_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


def config_api():
    from . import admin_bot

    return jsonify({'data': admin_bot.build_bot_configuration_snapshot()})


def send_test_message_api():
    """POST /bot/api/config/test-message — send a test message to a channel."""
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    channel_id = str(payload.get('channel_id', '')).strip()
    message = str(payload.get('message', '')).strip(
    ) or 'Test message from Open Mic Odyssey Bot API'
    if not channel_id:
        return jsonify({'error': {'code': 'missing_channel_id', 'message': 'channel_id is required'}}), 400

    token = _discord_bot_token()
    if not token:
        return jsonify({'error': {'code': 'no_bot_token', 'message': 'Bot token not configured'}}), 400

    from .bot_utils import _discord_api_post
    result = _discord_api_post(
        f'/channels/{channel_id}/messages', {'content': message})
    if result is None:
        return jsonify({'error': {'code': 'discord_api_error', 'message': 'Failed to send message'}}), 502

    logger.info("Test message sent to channel %s: msg=%s",
                channel_id, result.get('id'))
    return jsonify({'data': {'channel_id': channel_id, 'message_id': result.get('id')}})


def send_test_message_page_action():
    """POST /bot/config/test-message — page action."""
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_config_scope_error()

    channel_id = str(request.form.get('channel_id', '')).strip()
    message = str(request.form.get('message', '')).strip(
    ) or 'Test message from Open Mic Odyssey Bot API'

    token = _discord_bot_token()
    if not token:
        return redirect(url_for('bot.commands_page', error='no-bot-token'))

    from .bot_utils import _discord_api_post
    result = _discord_api_post(
        f'/channels/{channel_id}/messages', {'content': message})
    if result is None:
        return redirect(url_for('bot.commands_page', error='test-message-failed'))

    logger.info("Test message sent via page: channel=%s msg=%s",
                channel_id, result.get('id'))
    return redirect(url_for('bot.commands_page', saved='test-message-sent'))


def set_active_guild_api():
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    try:
        guild = admin_bot._set_active_guild_id(
            admin_bot._parse_required_int(payload.get('guild_id'), 'guild_id'))
        logger.info("Active guild set via API: guild_id=%s",
                    payload.get('guild_id'))
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409

    return jsonify({'data': guild})


def set_active_guild_page_action():
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_config_scope_error()

    try:
        admin_bot._set_active_guild_id(
            admin_bot._parse_required_int(request.form.get('guild_id'), 'guild_id'))
    except admin_bot.ConfigError:
        return admin_bot._page_config_binding_error()

    return redirect(url_for('bot.guild_page', saved='guild-updated'))


def upsert_channel_binding_api():
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    try:
        binding = admin_bot._upsert_channel_binding(
            admin_bot._parse_binding_key(payload.get('binding_key')),
            admin_bot._parse_required_int(
                payload.get('channel_id'), 'channel_id'),
        )
        logger.info("Channel binding upserted via API: key=%s channel=%s",
                    payload.get('binding_key'), payload.get('channel_id'))
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409

    return jsonify({'data': binding})


def upsert_channel_binding_page_action():
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_config_scope_error()

    try:
        admin_bot._upsert_channel_binding(
            admin_bot._parse_binding_key(request.form.get('binding_key')),
            admin_bot._parse_required_int(
                request.form.get('channel_id'), 'channel_id'),
        )
    except admin_bot.ConfigError:
        return admin_bot._page_config_binding_error()

    return redirect(url_for('bot.config_page', saved='channel-binding-saved'))


def delete_channel_binding_api(binding_key: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        admin_bot._delete_channel_binding(binding_key)
        logger.info("Channel binding deleted via API: key=%s", binding_key)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'binding_not_found', 'message': 'Channel binding was not found.'}}), 404

    return jsonify({'data': {'binding_key': binding_key, 'deleted': True}})


def delete_channel_binding_page_action(binding_key: str):
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_config_scope_error()

    try:
        admin_bot._delete_channel_binding(binding_key)
    except (admin_bot.ConfigError, KeyError):
        return admin_bot._page_config_binding_error()

    return redirect(url_for('bot.config_page', saved='channel-binding-deleted'))


def upsert_role_binding_api():
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    try:
        binding = admin_bot._upsert_role_binding(
            admin_bot._parse_binding_key(payload.get('binding_key')),
            admin_bot._parse_required_int(payload.get('role_id'), 'role_id'),
        )
        logger.info("Role binding upserted via API: key=%s role=%s",
                    payload.get('binding_key'), payload.get('role_id'))
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409

    return jsonify({'data': binding})


def upsert_role_binding_page_action():
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_config_scope_error()

    try:
        admin_bot._upsert_role_binding(
            admin_bot._parse_binding_key(request.form.get('binding_key')),
            admin_bot._parse_required_int(
                request.form.get('role_id'), 'role_id'),
        )
    except admin_bot.ConfigError:
        return admin_bot._page_config_binding_error()

    return redirect(url_for('bot.config_page', saved='role-binding-saved'))


def delete_role_binding_api(binding_key: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        admin_bot._delete_role_binding(binding_key)
        logger.info("Role binding deleted via API: key=%s", binding_key)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_config_binding', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'binding_not_found', 'message': 'Role binding was not found.'}}), 404

    return jsonify({'data': {'binding_key': binding_key, 'deleted': True}})


def delete_role_binding_page_action(binding_key: str):
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_config_scope_error()

    try:
        admin_bot._delete_role_binding(binding_key)
    except (admin_bot.ConfigError, KeyError):
        return admin_bot._page_config_binding_error()

    return redirect(url_for('bot.config_page', saved='role-binding-deleted'))


def enable_syndication_source_api(source_key: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        source_state = admin_bot._set_syndication_source_enabled(
            source_key, True)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'syndication_source_not_found', 'message': 'Configured syndication source was not found.'}}), 404

    return jsonify({'data': source_state})


def enable_syndication_source_page_action(source_key: str):
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_config_scope_error()

    try:
        admin_bot._set_syndication_source_enabled(source_key, True)
    except admin_bot.ConfigError:
        return admin_bot._page_config_error()
    except KeyError:
        return redirect(url_for('bot.config_page', error='source-not-found'))

    return redirect(url_for('bot.config_page', saved='source-enabled'))


def disable_syndication_source_api(source_key: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        source_state = admin_bot._set_syndication_source_enabled(
            source_key, False)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except KeyError:
        return jsonify({'error': {'code': 'syndication_source_not_found', 'message': 'Configured syndication source was not found.'}}), 404

    return jsonify({'data': source_state})


def disable_syndication_source_page_action(source_key: str):
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_config_scope_error()

    try:
        admin_bot._set_syndication_source_enabled(source_key, False)
    except admin_bot.ConfigError:
        return admin_bot._page_config_error()
    except KeyError:
        return redirect(url_for('bot.config_page', error='source-not-found'))

    return redirect(url_for('bot.config_page', saved='source-disabled'))
