from __future__ import annotations

import logging
from typing import cast

from flask import jsonify, render_template, request

logger = logging.getLogger(__name__)


def mileage_page():
    from . import admin_bot

    return render_template(
        'mileage.html',
        mileage_snapshot=admin_bot.build_mileage_index_snapshot(
            search=str(request.args.get('q') or '').strip(),
            tier_id=str(request.args.get('tier_id') or '').strip() or None,
        ),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


def mileage_detail_page(user_id: str):
    from . import admin_bot

    try:
        mileage_detail_snapshot = admin_bot.build_mileage_detail_snapshot(
            user_id)
    except admin_bot.ConfigError:
        return admin_bot._page_mileage_config_error(user_id)
    except admin_bot.MileageNotFoundError:
        return admin_bot._page_mileage_not_found_error()

    return render_template(
        'mileage_detail.html',
        mileage_detail_snapshot=mileage_detail_snapshot,
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


def mileage_users_api():
    from . import admin_bot

    snapshot = admin_bot.build_mileage_index_snapshot(
        search=str(request.args.get('q') or '').strip(),
        tier_id=str(request.args.get('tier_id') or '').strip() or None,
    )
    return jsonify({
        'data': snapshot['users'],
        'meta': {
            'status': snapshot['status'],
            'generated_at': snapshot['generated_at'],
            'guild_id': snapshot['guild_id'],
        }
    })


def mileage_user_detail_api(user_id: str):
    from . import admin_bot

    try:
        snapshot = admin_bot.build_mileage_detail_snapshot(user_id)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_config', 'message': str(exc)}}), 409
    except admin_bot.MileageNotFoundError:
        return jsonify({'error': {'code': 'mileage_not_found', 'message': 'Mileage user was not found.'}}), 404

    return jsonify({
        'data': snapshot['user'],
        'meta': {
            'generated_at': snapshot['generated_at'],
            'guild_id': snapshot['guild_id'],
        }
    })


def mileage_user_events_api(user_id: str):
    from . import admin_bot

    try:
        snapshot = admin_bot.build_mileage_detail_snapshot(user_id)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_config', 'message': str(exc)}}), 409
    except admin_bot.MileageNotFoundError:
        return jsonify({'error': {'code': 'mileage_not_found', 'message': 'Mileage user was not found.'}}), 404

    user = cast(dict[str, object], snapshot['user'])
    return jsonify({
        'data': user['events'],
        'meta': {
            'generated_at': snapshot['generated_at'],
            'guild_id': snapshot['guild_id'],
        }
    })


def mileage_tiers_api():
    from . import admin_bot

    snapshot = admin_bot.build_mileage_index_snapshot(
        search=str(request.args.get('q') or '').strip(),
        tier_id=str(request.args.get('tier_id') or '').strip() or None,
    )
    return jsonify({
        'data': snapshot['tiers'],
        'meta': {
            'status': snapshot['status'],
            'generated_at': snapshot['generated_at'],
            'guild_id': snapshot['guild_id'],
        }
    })


def adjust_mileage_user_api(user_id: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('mileage.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    try:
        user, event = admin_bot._adjust_mileage_user(
            user_id,
            admin_bot._parse_required_text(payload.get(
                'display_name') or user_id, 'display_name'),
            admin_bot._parse_required_int(payload.get('delta'), 'delta'),
            admin_bot._parse_required_text(payload.get('reason'), 'reason'),
            str(payload.get('correlation_id') or '').strip() or None,
        )
        logger.info("Mileage adjusted via API: user=%s delta=%d",
                    user_id, payload.get('delta'))
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_config', 'message': str(exc)}}), 409
    except admin_bot.MileageValidationError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_action', 'message': str(exc)}}), 400

    return jsonify({'data': user, 'meta': {'event': event}})


def adjust_mileage_user_page_action(user_id: str):
    from request_ui_helpers import _mileage_page_redirect
    from . import admin_bot

    if not admin_bot._operator_can('mileage.write'):
        return admin_bot._page_mileage_scope_error(user_id)

    try:
        admin_bot._adjust_mileage_user(
            user_id,
            admin_bot._parse_required_text(request.form.get(
                'display_name') or user_id, 'display_name'),
            admin_bot._parse_required_int(request.form.get('delta'), 'delta'),
            admin_bot._parse_required_text(
                request.form.get('reason'), 'reason'),
            str(request.form.get('correlation_id') or '').strip() or None,
        )
    except admin_bot.ConfigError:
        return admin_bot._page_mileage_config_error(user_id)
    except admin_bot.MileageValidationError:
        return admin_bot._page_mileage_action_error(user_id)

    return _mileage_page_redirect(user_id, saved='mileage-adjusted')


def reverse_mileage_event_api(event_id: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('mileage.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    try:
        user, event = admin_bot._reverse_mileage_event(
            event_id,
            admin_bot._parse_required_text(payload.get('reason'), 'reason'),
        )
        logger.info("Mileage event reversed via API: event_id=%s", event_id)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_mileage_config', 'message': str(exc)}}), 409
    except admin_bot.MileageNotFoundError:
        return jsonify({'error': {'code': 'mileage_not_found', 'message': 'Mileage event was not found.'}}), 404
    except (admin_bot.MileageValidationError, admin_bot.MileageConflictError) as exc:
        return jsonify({'error': {'code': 'invalid_mileage_action', 'message': str(exc)}}), 409

    return jsonify({'data': user, 'meta': {'event': event}})


def reverse_mileage_event_page_action(event_id: str):
    from . import admin_bot

    if not admin_bot._operator_can('mileage.write'):
        return admin_bot._page_mileage_scope_error()
    try:
        user, _event = admin_bot._reverse_mileage_event(
            event_id,
            admin_bot._parse_required_text(
                request.form.get('reason'), 'reason'),
        )
    except admin_bot.ConfigError:
        return admin_bot._page_mileage_config_error()
    except admin_bot.MileageNotFoundError:
        return admin_bot._page_mileage_not_found_error()
    except (admin_bot.MileageValidationError, admin_bot.MileageConflictError):
        return admin_bot._page_mileage_action_error()

    return admin_bot._mileage_page_redirect(
        str(cast(dict[str, object], user['total'])['discord_user_id']),
        saved='mileage-reversed',
    )
