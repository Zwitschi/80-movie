from __future__ import annotations

import logging
from typing import cast

from flask import jsonify, render_template, request

logger = logging.getLogger(__name__)


def queues_page():
    from . import admin_bot

    return render_template(
        'queues.html',
        queue_index_snapshot=admin_bot.build_queue_index_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


def queue_detail_page(queue_id: str):
    from . import admin_bot

    try:
        queue_detail_snapshot = admin_bot.build_queue_detail_snapshot(queue_id)
    except admin_bot.ConfigError:
        return admin_bot._page_queue_config_error(queue_id)
    except admin_bot.QueueNotFoundError:
        return admin_bot._page_queue_not_found_error()

    return render_template(
        'queue_detail.html',
        queue_detail_snapshot=queue_detail_snapshot,
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


def queues_api():
    from . import admin_bot

    snapshot = admin_bot.build_queue_index_snapshot()
    return jsonify({
        'data': snapshot['queues'],
        'meta': {
            'status': snapshot['status'],
            'generated_at': snapshot['generated_at'],
        }
    })


def queue_detail_api(queue_id: str):
    from . import admin_bot

    try:
        snapshot = admin_bot.build_queue_detail_snapshot(queue_id)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except admin_bot.QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404

    return jsonify({
        'data': snapshot['queue'],
        'meta': {
            'events_count': len(snapshot['events']),
            'generated_at': snapshot['generated_at'],
        }
    })


def queue_events_api(queue_id: str):
    from . import admin_bot

    try:
        snapshot = admin_bot.build_queue_detail_snapshot(queue_id)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except admin_bot.QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404

    return jsonify({'data': snapshot['events'], 'meta': {'generated_at': snapshot['generated_at']}})


def create_queue_api():
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    try:
        queue = admin_bot._create_queue(
            admin_bot._parse_required_text(
                payload.get('queue_id'), 'queue_id'),
            admin_bot._parse_required_int(payload.get('guild_id'), 'guild_id'),
            admin_bot._parse_required_text(payload.get('label'), 'label'),
        )
        logger.info("Queue created via API: queue_id=%s", payload.get('queue_id'))
    except admin_bot.ConfigError as exc:
        logger.warning("Queue create config error: %s", exc)
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409

    return jsonify({'data': queue})


def create_queue_page_action():
    from . import admin_bot

    if not admin_bot._operator_can('queue.write'):
        return admin_bot._page_queue_scope_error()

    try:
        queue = admin_bot._create_queue(
            admin_bot._parse_required_text(
                request.form.get('queue_id'), 'queue_id'),
            admin_bot._parse_required_int(
                request.form.get('guild_id'), 'guild_id'),
            admin_bot._parse_required_text(request.form.get('label'), 'label'),
        )
    except admin_bot.ConfigError:
        return admin_bot._page_queue_config_error()

    return admin_bot._queue_page_redirect(
        str(cast(dict[str, object], queue['summary'])['queue_id']),
        saved='queue-created',
    )


def advance_queue_api(queue_id: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error

    try:
        queue, event = admin_bot._advance_queue(queue_id)
        logger.info("Queue advanced via API: queue_id=%s", queue_id)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except admin_bot.QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except (admin_bot.QueuePausedError, admin_bot.QueueConflictError) as exc:
        return jsonify({'error': {'code': 'queue_conflict', 'message': str(exc)}}), 409

    return jsonify({'data': queue, 'meta': {'event': event}})


def advance_queue_page_action(queue_id: str):
    from . import admin_bot

    if not admin_bot._operator_can('queue.write'):
        return admin_bot._page_queue_scope_error(queue_id)
    try:
        admin_bot._advance_queue(queue_id)
    except admin_bot.ConfigError:
        return admin_bot._page_queue_config_error(queue_id)
    except admin_bot.QueueNotFoundError:
        return admin_bot._page_queue_not_found_error()
    except (admin_bot.QueuePausedError, admin_bot.QueueConflictError):
        return admin_bot._page_queue_action_error(queue_id)
    return admin_bot._queue_page_redirect(queue_id, saved='queue-advanced')


def remove_queue_entry_api(queue_id: str, entry_id: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    try:
        queue, event = admin_bot._remove_queue_entry(
            queue_id, entry_id, str(payload.get('reason') or '').strip())
        logger.info("Queue entry removed via API: queue_id=%s entry_id=%s", queue_id, entry_id)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except admin_bot.QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except admin_bot.QueueEntryNotFoundError:
        return jsonify({'error': {'code': 'queue_entry_not_found', 'message': 'Queue entry was not found.'}}), 404

    return jsonify({'data': queue, 'meta': {'event': event}})


def remove_queue_entry_page_action(queue_id: str, entry_id: str):
    from . import admin_bot

    if not admin_bot._operator_can('queue.write'):
        return admin_bot._page_queue_scope_error(queue_id)
    try:
        admin_bot._remove_queue_entry(
            queue_id,
            entry_id,
            str(request.form.get('reason') or '').strip(),
        )
    except admin_bot.ConfigError:
        return admin_bot._page_queue_config_error(queue_id)
    except admin_bot.QueueNotFoundError:
        return admin_bot._page_queue_not_found_error()
    except admin_bot.QueueEntryNotFoundError:
        return admin_bot._page_queue_action_error(queue_id)
    return admin_bot._queue_page_redirect(queue_id, saved='entry-removed')


def move_queue_entry_api(queue_id: str, entry_id: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error

    payload = admin_bot._request_data()
    try:
        queue, event = admin_bot._move_queue_entry(
            queue_id,
            entry_id,
            admin_bot._parse_required_int(payload.get(
                'target_position'), 'target_position'),
            str(payload.get('reason') or '').strip(),
        )
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except admin_bot.QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except admin_bot.QueueEntryNotFoundError:
        return jsonify({'error': {'code': 'queue_entry_not_found', 'message': 'Queue entry was not found.'}}), 404
    except admin_bot.QueueValidationError as exc:
        return jsonify({'error': {'code': 'invalid_queue_action', 'message': str(exc)}}), 400
    except admin_bot.QueuePausedError as exc:
        return jsonify({'error': {'code': 'queue_conflict', 'message': str(exc)}}), 409

    return jsonify({'data': queue, 'meta': {'event': event}})


def move_queue_entry_page_action(queue_id: str, entry_id: str):
    from . import admin_bot

    if not admin_bot._operator_can('queue.write'):
        return admin_bot._page_queue_scope_error(queue_id)
    try:
        admin_bot._move_queue_entry(
            queue_id,
            entry_id,
            admin_bot._parse_required_int(request.form.get(
                'target_position'), 'target_position'),
            str(request.form.get('reason') or '').strip(),
        )
    except admin_bot.ConfigError:
        return admin_bot._page_queue_config_error(queue_id)
    except (admin_bot.QueueEntryNotFoundError, admin_bot.QueueValidationError, admin_bot.QueuePausedError):
        return admin_bot._page_queue_action_error(queue_id)
    except admin_bot.QueueNotFoundError:
        return admin_bot._page_queue_not_found_error()
    return admin_bot._queue_page_redirect(queue_id, saved='entry-moved')


def pause_queue_api(queue_id: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error
    payload = admin_bot._request_data()
    try:
        queue, event = admin_bot._pause_queue(
            queue_id, str(payload.get('reason') or '').strip())
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except admin_bot.QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except admin_bot.QueueConflictError as exc:
        return jsonify({'error': {'code': 'queue_conflict', 'message': str(exc)}}), 409

    return jsonify({'data': queue, 'meta': {'event': event}})


def pause_queue_page_action(queue_id: str):
    from . import admin_bot

    if not admin_bot._operator_can('queue.write'):
        return admin_bot._page_queue_scope_error(queue_id)
    try:
        admin_bot._pause_queue(queue_id, str(
            request.form.get('reason') or '').strip())
    except admin_bot.ConfigError:
        return admin_bot._page_queue_config_error(queue_id)
    except admin_bot.QueueNotFoundError:
        return admin_bot._page_queue_not_found_error()
    except admin_bot.QueueConflictError:
        return admin_bot._page_queue_action_error(queue_id)
    return admin_bot._queue_page_redirect(queue_id, saved='queue-paused')


def resume_queue_api(queue_id: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error
    try:
        queue, event = admin_bot._resume_queue(queue_id)
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except admin_bot.QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except admin_bot.QueueConflictError as exc:
        return jsonify({'error': {'code': 'queue_conflict', 'message': str(exc)}}), 409

    return jsonify({'data': queue, 'meta': {'event': event}})


def resume_queue_page_action(queue_id: str):
    from . import admin_bot

    if not admin_bot._operator_can('queue.write'):
        return admin_bot._page_queue_scope_error(queue_id)
    try:
        admin_bot._resume_queue(queue_id)
    except admin_bot.ConfigError:
        return admin_bot._page_queue_config_error(queue_id)
    except admin_bot.QueueNotFoundError:
        return admin_bot._page_queue_not_found_error()
    except admin_bot.QueueConflictError:
        return admin_bot._page_queue_action_error(queue_id)
    return admin_bot._queue_page_redirect(queue_id, saved='queue-resumed')


def clear_queue_api(queue_id: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('queue.write')
    if scope_error is not None:
        return scope_error
    payload = admin_bot._request_data()
    dry_run = bool(payload.get('dry_run', False))
    try:
        queue, event = admin_bot._clear_queue(
            queue_id,
            str(payload.get('reason') or '').strip(),
            str(payload.get('confirm') or '').strip(),
            dry_run=dry_run,
        )
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_queue_config', 'message': str(exc)}}), 409
    except admin_bot.QueueNotFoundError:
        return jsonify({'error': {'code': 'queue_not_found', 'message': 'Queue was not found.'}}), 404
    except admin_bot.QueueValidationError as exc:
        return jsonify({'error': {'code': 'invalid_queue_action', 'message': str(exc)}}), 400

    return jsonify({'data': queue, 'meta': {'event': event, 'dry_run': dry_run}})


def clear_queue_page_action(queue_id: str):
    from . import admin_bot

    if not admin_bot._operator_can('queue.write'):
        return admin_bot._page_queue_scope_error(queue_id)
    try:
        admin_bot._clear_queue(
            queue_id,
            str(request.form.get('reason') or '').strip(),
            str(request.form.get('confirm') or '').strip(),
        )
    except admin_bot.ConfigError:
        return admin_bot._page_queue_config_error(queue_id)
    except admin_bot.QueueNotFoundError:
        return admin_bot._page_queue_not_found_error()
    except admin_bot.QueueValidationError:
        return admin_bot._page_queue_confirmation_error(queue_id)
    return admin_bot._queue_page_redirect(queue_id, saved='queue-cleared')
