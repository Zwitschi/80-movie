from __future__ import annotations

from typing import cast

from flask import redirect, request, url_for


def _request_data() -> dict[str, object]:
    if request.is_json:
        return cast(dict[str, object], request.get_json(silent=True) or {})
    return {key: value for key, value in request.form.items()}


def _parse_binding_key(raw_value: object, field_name: str = 'binding_key') -> str:
    from . import admin_bot

    binding_key = str(raw_value or '').strip()
    if not binding_key:
        raise admin_bot.ConfigError(f'{field_name} is required.')
    return binding_key


def _parse_required_text(raw_value: object, field_name: str) -> str:
    from . import admin_bot

    value = str(raw_value or '').strip()
    if not value:
        raise admin_bot.ConfigError(f'{field_name} is required.')
    return value


def _parse_required_int(raw_value: object, field_name: str) -> int:
    from . import admin_bot

    text = str(raw_value or '').strip()
    if not text:
        raise admin_bot.ConfigError(f'{field_name} is required.')
    try:
        return int(text)
    except ValueError as exc:
        raise admin_bot.ConfigError(
            f'{field_name} must be an integer.') from exc


def _page_syndication_scope_error():
    return redirect(url_for('bot.syndication_page', error='operator-scope-required'))


def _page_syndication_config_error():
    return redirect(url_for('bot.syndication_page', error='invalid-syndication-config'))


def _page_config_scope_error():
    return redirect(url_for('bot.config_page', error='operator-scope-required'))


def _page_config_error():
    return redirect(url_for('bot.config_page', error='invalid-syndication-config'))


def _page_config_binding_error():
    return redirect(url_for('bot.config_page', error='invalid-config-binding'))


def _page_commands_scope_error():
    return redirect(url_for('bot.commands_page', error='operator-scope-required'))


def _page_commands_error():
    return redirect(url_for('bot.commands_page', error='invalid-syndication-config'))


def _queue_page_redirect(queue_id: str | None = None, **params: str):
    if queue_id:
        return redirect(url_for('bot.queue_detail_page', queue_id=queue_id, **params))
    return redirect(url_for('bot.queues_page', **params))


def _page_queue_scope_error(queue_id: str | None = None):
    return _queue_page_redirect(queue_id, error='operator-scope-required')


def _page_queue_config_error(queue_id: str | None = None):
    return _queue_page_redirect(queue_id, error='invalid-queue-config')


def _page_queue_action_error(queue_id: str | None = None):
    return _queue_page_redirect(queue_id, error='invalid-queue-action')


def _page_queue_not_found_error(queue_id: str | None = None):
    return _queue_page_redirect(queue_id, error='queue-not-found')


def _page_queue_confirmation_error(queue_id: str | None = None):
    return _queue_page_redirect(queue_id, error='queue-clear-confirmation-required')


def _mileage_page_redirect(user_id: str | None = None, **params: str):
    if user_id:
        return redirect(url_for('bot.mileage_detail_page', user_id=user_id, **params))
    return redirect(url_for('bot.mileage_page', **params))


def _page_mileage_scope_error(user_id: str | None = None):
    return _mileage_page_redirect(user_id, error='operator-scope-required')


def _page_mileage_config_error(user_id: str | None = None):
    return _mileage_page_redirect(user_id, error='invalid-mileage-config')


def _page_mileage_action_error(user_id: str | None = None):
    return _mileage_page_redirect(user_id, error='invalid-mileage-action')


def _page_mileage_not_found_error(user_id: str | None = None):
    return _mileage_page_redirect(user_id, error='mileage-not-found')
