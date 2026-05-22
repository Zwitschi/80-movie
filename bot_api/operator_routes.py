from __future__ import annotations

from flask import jsonify, redirect, render_template, request, url_for

from . import bot_operator_repo, bot_operator_service


def _operator_not_found_response():
    if request.path.startswith('/bot/api/'):
        return jsonify({
            'error': {
                'code': 'operator_not_found',
                'message': 'Bot operator record was not found.',
            }
        }), 404

    return redirect(url_for('bot.operators_page', error='operator-not-found'))


def _invalid_operator_scopes_response():
    if request.path.startswith('/bot/api/'):
        return jsonify({
            'error': {
                'code': 'invalid_operator_scopes',
                'message': 'At least one valid operator scope is required.',
            }
        }), 400

    return redirect(url_for('bot.operators_page', error='invalid-operator-scopes'))


def _update_operator_active(user_id: str, is_active: bool):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('operators.write')
    if scope_error is not None:
        return scope_error

    before_state = bot_operator_repo.get_bot_operator_by_discord_user_id(
        user_id)
    operator_record = bot_operator_repo.set_bot_operator_active(
        user_id, is_active)
    if operator_record is None:
        return _operator_not_found_response()
    admin_bot._record_bot_audit_event(
        action_key='operator.enabled' if is_active else 'operator.disabled',
        target_type='operator',
        target_key=user_id,
        before_state=before_state,
        after_state=operator_record,
    )
    return operator_record


def _update_operator_scopes(user_id: str, raw_scopes: object):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('operators.write')
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
    admin_bot._record_bot_audit_event(
        action_key='operator.scopes.updated',
        target_type='operator',
        target_key=user_id,
        before_state=before_state,
        after_state=operator_record,
    )
    return operator_record


def operators_page():
    return render_template(
        'operators.html',
        operators=bot_operator_repo.list_bot_operators(),
        save_success=request.args.get('saved') == '1',
        error=request.args.get('error'),
    )


def operators_api():
    return jsonify({'data': bot_operator_repo.list_bot_operators()})


def disable_operator_api(user_id: str):
    operator_record = _update_operator_active(user_id, False)
    if not isinstance(operator_record, dict):
        return operator_record
    return jsonify({'data': operator_record})


def disable_operator_page_action(user_id: str):
    operator_record = _update_operator_active(user_id, False)
    if not isinstance(operator_record, dict):
        return operator_record
    return redirect(url_for('bot.operators_page', saved='1'))


def enable_operator_api(user_id: str):
    operator_record = _update_operator_active(user_id, True)
    if not isinstance(operator_record, dict):
        return operator_record
    return jsonify({'data': operator_record})


def enable_operator_page_action(user_id: str):
    operator_record = _update_operator_active(user_id, True)
    if not isinstance(operator_record, dict):
        return operator_record
    return redirect(url_for('bot.operators_page', saved='1'))


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


def update_operator_scopes_page_action(user_id: str):
    operator_record = _update_operator_scopes(
        user_id, request.form.get('scopes', ''))
    if not isinstance(operator_record, dict):
        return operator_record
    return redirect(url_for('bot.operators_page', saved='1'))
