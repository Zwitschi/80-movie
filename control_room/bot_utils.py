"""Shared, Flask-free helpers for the bot control-room surface.

All functions here are pure or depend only on stdlib / bot domain models.
Nothing in this module touches Flask's request/session/current_app context.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast
from urllib.error import HTTPError

# ---------------------------------------------------------------------------
# Discord HTTP constant (used by request-building helpers)
# ---------------------------------------------------------------------------

DISCORD_HTTP_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/136.0.0.0 Safari/537.36'
)

# ---------------------------------------------------------------------------
# Bot model imports (optional — bot/ may not be on the Python path in some
# deployment configurations, matching the try/except pattern in admin_bot.py)
# ---------------------------------------------------------------------------

try:
    from bot.omo_bot.config import BotConfig, BotRuntimeSettings, ConfigError
    from bot.omo_bot.models import SyndicationSourceState
except ModuleNotFoundError:
    BotConfig = None  # type: ignore[misc,assignment]
    BotRuntimeSettings = None  # type: ignore[misc,assignment]
    ConfigError = RuntimeError  # type: ignore[misc,assignment]
    SyndicationSourceState = None  # type: ignore[misc,assignment]

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Generic audit / state serialization
# ---------------------------------------------------------------------------


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


def _bool_status(configured: bool) -> str:
    return 'ok' if configured else 'missing_config'


def _health_components(health: dict[str, object]) -> dict[str, Any]:
    return cast(dict[str, Any], health['components'])


# ---------------------------------------------------------------------------
# Session timestamp parsing
# ---------------------------------------------------------------------------


def _parse_session_timestamp(raw_value: object) -> datetime | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Discord HTTP helpers
# ---------------------------------------------------------------------------


def _discord_avatar_url(discord_user: dict[str, object]) -> str | None:
    user_id = str(discord_user.get('id', '')).strip()
    avatar_hash = str(discord_user.get('avatar', '')).strip()
    if not user_id or not avatar_hash:
        return None
    return f'https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png'


def _decode_http_error(exc: HTTPError) -> str:
    try:
        body = exc.read().decode('utf-8', errors='replace').strip()
    except Exception:
        body = ''
    return body


def _discord_request_headers(*, access_token: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {
        'Accept': 'application/json',
        'User-Agent': DISCORD_HTTP_USER_AGENT,
    }
    if access_token:
        headers['Authorization'] = f'Bearer {access_token}'
    return headers


# ---------------------------------------------------------------------------
# Operator identity
# ---------------------------------------------------------------------------


def _operator_user_id(operator_identity: dict[str, object]) -> str:
    return str(operator_identity.get('user_id', '')).strip()


# ---------------------------------------------------------------------------
# Syndication domain helpers
# ---------------------------------------------------------------------------


def _default_syndication_state(source_key: str) -> 'SyndicationSourceState':
    return SyndicationSourceState(source_key=source_key)


def _manual_syndication_actions_supported(settings: 'BotRuntimeSettings') -> bool:
    return bool(settings.database_url)


def _syndication_last_poll_result(state: 'SyndicationSourceState') -> str:
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
    state: 'SyndicationSourceState',
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


def _configured_syndication_source(settings: 'BotRuntimeSettings', source_key: str) -> bool:
    return source_key in settings.syndication_sources


# ---------------------------------------------------------------------------
# Bot config factory
# ---------------------------------------------------------------------------


def _build_bot_config_from_runtime_settings(settings: 'BotRuntimeSettings') -> 'BotConfig':
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


# ---------------------------------------------------------------------------
# Mileage helpers
# ---------------------------------------------------------------------------


def _mileage_active_guild_id(settings: 'BotRuntimeSettings') -> int:
    if settings.guild_id is None:
        raise ConfigError(
            'An active guild id is required for mileage operations.'
        )
    return settings.guild_id
