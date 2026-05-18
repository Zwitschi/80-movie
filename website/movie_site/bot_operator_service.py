from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import current_app

from . import bot_operator_repo


BOT_OPS_ADMIN_SCOPE = 'ops.admin'


def _allowed_operator_ids() -> set[str]:
    configured = current_app.config.get('BOT_OPS_ALLOWED_USER_IDS', ())
    if isinstance(configured, str):
        return {value.strip() for value in configured.split(',') if value.strip()}

    return {str(value).strip() for value in configured if str(value).strip()}


def default_operator_scopes() -> list[str]:
    configured = current_app.config.get(
        'BOT_OPS_DEFAULT_SCOPES', ('ops.read',))
    if isinstance(configured, str):
        return [value.strip() for value in configured.split(',') if value.strip()]

    return [str(value).strip() for value in configured if str(value).strip()]


def normalize_operator_scopes(raw_scopes: object) -> list[str]:
    if isinstance(raw_scopes, str):
        return [value.strip() for value in raw_scopes.split(',') if value.strip()]

    if isinstance(raw_scopes, (list, tuple, set)):
        return [str(value).strip() for value in raw_scopes if str(value).strip()]

    return []


def has_operator_scope(raw_scopes: object, *required_scopes: str) -> bool:
    normalized_scopes = set(normalize_operator_scopes(raw_scopes))
    if BOT_OPS_ADMIN_SCOPE in normalized_scopes:
        return True

    return any(scope in normalized_scopes for scope in required_scopes)


def get_operator_access(user_id: str) -> dict[str, Any]:
    operator_record = bot_operator_repo.get_bot_operator_by_discord_user_id(
        user_id)
    if operator_record is not None:
        resolved_scopes = normalize_operator_scopes(
            operator_record.get('scopes') or [])
        return {
            'allowed': bool(operator_record.get('is_active')),
            'scopes': resolved_scopes or default_operator_scopes(),
            'operator_record': operator_record,
        }

    return {
        'allowed': user_id in _allowed_operator_ids(),
        'scopes': default_operator_scopes(),
        'operator_record': None,
    }


def persist_operator_login(
    *,
    operator_identity: dict[str, object],
    scopes: list[str],
    last_login_at: datetime,
) -> None:
    bot_operator_repo.upsert_bot_operator_login(
        user_id=str(operator_identity.get('user_id', '')).strip(),
        username=str(operator_identity.get('username', '')).strip(),
        global_name=str(operator_identity.get('global_name', '')).strip(),
        avatar_url=(
            str(operator_identity.get('avatar_url')).strip()
            if operator_identity.get('avatar_url')
            else None
        ),
        scopes=scopes,
        last_login_at=last_login_at,
    )
