"""Shared, Flask-free helpers for the bot control-room surface.

All functions here are pure or depend only on stdlib / bot domain models.
Nothing in this module touches Flask's request/session/current_app context.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy bot imports -- allow bot_api to start even without bot/ on Python path.
# from __future__ import annotations makes all annotations strings.
# pyright: reportInvalidTypeForm=false, reportCallIssue=false, reportAttributeAccessIssue=false
# ---------------------------------------------------------------------------

_BOT_UTILS_IMPORT_ERROR: ImportError | None = None

try:
    from bot.models import SyndicationSourceState
    from bot.config import BotConfig, BotRuntimeSettings, ConfigError
    _BOT_UTILS_AVAILABLE = True
except ImportError as _exc:
    _BOT_UTILS_IMPORT_ERROR = _exc
    _BOT_UTILS_AVAILABLE = False

    class _BotUtilsMissingStubError(Exception):
        """Placeholder for a bot.* exception when bot/ is not available."""

    ConfigError = _BotUtilsMissingStubError  # type: ignore[assignment]
    BotConfig = _BotUtilsMissingStubError  # type: ignore[assignment]
    BotRuntimeSettings = _BotUtilsMissingStubError  # type: ignore[assignment]
    SyndicationSourceState = _BotUtilsMissingStubError  # type: ignore[assignment]


def _require_bot_utils_module() -> None:
    """Raise ImportError if bot/ failed to import. Call before using runtime symbols."""
    if not _BOT_UTILS_AVAILABLE:
        msg = (
            "Bot module is not available. The bot/ package must be on the "
            "Python path (deploy from repo root or set PYTHONPATH)."
        )
        if _BOT_UTILS_IMPORT_ERROR is not None:
            raise ImportError(msg) from _BOT_UTILS_IMPORT_ERROR
        raise ImportError(msg)

# ---------------------------------------------------------------------------
# Discord HTTP constant (used by request-building helpers)
# ---------------------------------------------------------------------------


DISCORD_HTTP_USER_AGENT = (
    'OpenMicOdysseyBot/1.0 (+https://www.openmicodyssey.com)'
)


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
# Discord API fetchers (bot token auth)
# ---------------------------------------------------------------------------

DISCORD_API_BASE = 'https://discord.com/api/v10'


def _discord_bot_token() -> str | None:
    """Read the bot token from env, preferring OMO_DISCORD_TOKEN."""
    import os
    return os.environ.get('OMO_DISCORD_TOKEN') or os.environ.get('DISCORD_TOKEN')


def _discord_bot_headers() -> dict[str, str]:
    token = _discord_bot_token()
    if not token:
        return _discord_request_headers()
    return {
        'Accept': 'application/json',
        'User-Agent': DISCORD_HTTP_USER_AGENT,
        'Authorization': f'Bot {token}',
    }


def _discord_api_get(path: str) -> dict[str, Any] | list[Any] | None:
    """Make a GET request to the Discord API with bot token auth."""
    headers = _discord_bot_headers()
    if 'Authorization' not in headers:
        logger.warning("Discord API call skipped: no bot token configured")
        return None
    url = f'{DISCORD_API_BASE}{path}'
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            data: Any = json.loads(resp.read().decode('utf-8'))
            return data
    except HTTPError as exc:
        logger.error("Discord API HTTP %s on GET %s: %s",
                     exc.code, path, _decode_http_error(exc))
        return None
    except URLError as exc:
        logger.error("Discord API connection error on GET %s: %s",
                     path, exc.reason)
        return None
    except Exception as exc:
        logger.error("Discord API unexpected error on GET %s: %s", path, exc)
        return None


def _fetch_discord_guild(guild_id: int) -> dict[str, Any] | None:
    """Fetch guild metadata from Discord API."""
    data = _discord_api_get(f'/guilds/{guild_id}')
    if isinstance(data, dict):
        return {
            'id': data.get('id'),
            'name': data.get('name'),
            'icon': data.get('icon'),
            'member_count': data.get('approximate_member_count'),
            'features': data.get('features', []),
            'description': data.get('description'),
            'premium_tier': data.get('premium_tier'),
            'preferred_locale': data.get('preferred_locale'),
        }
    return None


def _fetch_discord_channels(guild_id: int) -> list[dict[str, Any]]:
    """Fetch channel list from Discord API."""
    data = _discord_api_get(f'/guilds/{guild_id}/channels')
    if isinstance(data, list):
        return [
            {
                'id': ch.get('id'),
                'name': ch.get('name'),
                'type': ch.get('type'),
                'parent_id': ch.get('parent_id'),
                'position': ch.get('position'),
            }
            for ch in data
        ]
    return []


def _fetch_discord_roles(guild_id: int) -> list[dict[str, Any]]:
    """Fetch role list from Discord API."""
    data = _discord_api_get(f'/guilds/{guild_id}/roles')
    if isinstance(data, list):
        return [
            {
                'id': r.get('id'),
                'name': r.get('name'),
                'color': r.get('color'),
                'position': r.get('position'),
                'permissions': r.get('permissions'),
                'managed': r.get('managed'),
                'mentionable': r.get('mentionable'),
            }
            for r in data
        ]
    return []


def _fetch_discord_members(guild_id: int, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch member list from Discord API."""
    data = _discord_api_get(f'/guilds/{guild_id}/members?limit={limit}')
    if isinstance(data, list):
        return [
            {
                'user': {
                    'id': m.get('user', {}).get('id'),
                    'username': m.get('user', {}).get('username'),
                    'global_name': m.get('user', {}).get('global_name'),
                    'avatar': m.get('user', {}).get('avatar'),
                },
                'nick': m.get('nick'),
                'roles': m.get('roles', []),
                'joined_at': m.get('joined_at'),
            }
            for m in data
        ]
    return []


def _discord_api_post(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Make a POST request to the Discord API with bot token auth."""
    headers = dict(_discord_bot_headers())
    headers['Content-Type'] = 'application/json'
    if 'Authorization' not in headers:
        logger.warning("Discord API POST skipped: no bot token configured")
        return None
    url = f'{DISCORD_API_BASE}{path}'
    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = Request(url, data=data_bytes, headers=headers)
        with urlopen(req, timeout=10) as resp:
            result: Any = json.loads(resp.read().decode('utf-8'))
            return result
    except HTTPError as exc:
        logger.error("Discord API HTTP %s on POST %s: %s",
                     exc.code, path, _decode_http_error(exc))
        return None
    except URLError as exc:
        logger.error("Discord API connection error on POST %s: %s",
                     path, exc.reason)
        return None
    except Exception as exc:
        logger.error("Discord API unexpected error on POST %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Operator identity
# ---------------------------------------------------------------------------


def _operator_user_id(operator_identity: dict[str, object]) -> str:
    return str(operator_identity.get('user_id', '')).strip()


# ---------------------------------------------------------------------------
# Syndication domain helpers
# ---------------------------------------------------------------------------


def _default_syndication_state(source_key: str) -> SyndicationSourceState:
    return SyndicationSourceState(source_key=source_key)


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


def _syndication_source_status(state: SyndicationSourceState, *, due_now: bool,) -> str:
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


def _configured_syndication_source(settings: BotRuntimeSettings, source_key: str) -> bool:
    return source_key in settings.syndication_sources


# ---------------------------------------------------------------------------
# Bot config factory
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Bot presence / heartbeat
# ---------------------------------------------------------------------------


def _read_bot_presence(database_url: str | None = None) -> dict[str, Any] | None:
    """Read latest heartbeat from bot_presence table."""
    import os
    dsn = database_url or os.environ.get(
        'DATABASE_URL') or os.environ.get('OMO_DATABASE_URL')
    if not dsn:
        return None
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT worker_id, last_seen_at, state, started_at "
                    "FROM bot_presence ORDER BY last_seen_at DESC LIMIT 1"
                )
                row = cur.fetchone()
                if row:
                    return {
                        'worker_id': row['worker_id'],
                        'last_seen_at': row['last_seen_at'].isoformat() if row['last_seen_at'] else None,
                        'state': row['state'],
                        'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                        'seconds_since_seen': (
                            int((_utcnow() -
                                row['last_seen_at']).total_seconds())
                            if row['last_seen_at'] else None
                        ),
                    }
                return None
        finally:
            conn.close()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Mileage helpers
# ---------------------------------------------------------------------------


def _mileage_active_guild_id(settings: BotRuntimeSettings) -> int:
    if settings.guild_id is None:
        raise ConfigError(
            'An active guild id is required for mileage operations.'
        )
    return settings.guild_id
