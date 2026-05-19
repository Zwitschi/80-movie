"""Shared configuration helpers for all OMO services.

Provides environment variable loading and default config values
used across website, control room, and bot API services.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def find_env_file(start_path: Optional[Path] = None) -> Optional[Path]:
    """Search for .env file starting from start_path, walking up to root."""
    if start_path is None:
        start_path = Path.cwd()

    current = start_path
    while current != current.parent:
        env_path = current / ".env"
        if env_path.exists():
            return env_path
        current = current.parent
    return None


def load_dotenv_files(*paths: Path) -> None:
    """Load multiple .env files in order. Later files override earlier ones."""
    for env_path in paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)


def get_env_str(key: str, default: str = "") -> str:
    """Get environment variable as string."""
    return os.getenv(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    """Get environment variable as integer."""
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def get_env_tuple(key: str, default: tuple = ()) -> tuple:
    """Get comma-separated environment variable as tuple."""
    raw = os.getenv(key, "")
    if not raw:
        return default
    return tuple(v.strip() for v in raw.split(",") if v.strip())


def get_current_year() -> int:
    """Get current UTC year or override from env."""
    return int(os.getenv("CURRENT_YEAR", str(datetime.now(timezone.utc).year)))


# Website config values
def get_website_config_values() -> dict:
    """Get website-specific configuration values from environment."""
    return {
        "SITE_URL": get_env_str("SITE_URL", "https://www.openmicodyssey.com"),
        "DATABASE_URL": get_env_str("DATABASE_URL", "postgresql://user:password@localhost/omo"),
        "DATA_SOURCE": get_env_str("DATA_SOURCE", "DB"),
        "CURRENT_YEAR": get_current_year(),
        "MAPBOX_ACCESS_TOKEN": get_env_str("MAPBOX_ACCESS_TOKEN", ""),
        "SECRET_KEY": get_env_str("SECRET_KEY", "dev-secret-key-change-in-production"),
        "ADMIN_USERNAME": get_env_str("ADMIN_USERNAME", "admin"),
    }


# Control room config values
def get_control_room_config_values() -> dict:
    """Get control room-specific configuration values from environment."""
    return {
        "DATABASE_URL": get_env_str("DATABASE_URL", "postgresql://user:password@localhost/omo"),
        "SECRET_KEY": get_env_str("SECRET_KEY", "dev-secret-key-change-in-production"),
        "BOT_OPS_DISCORD_CLIENT_ID": get_env_str(
            "OMO_DISCORD_CLIENT_ID",
            get_env_str("DISCORD_CLIENT_ID", ""),
        ),
        "BOT_OPS_DISCORD_CLIENT_SECRET": get_env_str(
            "OMO_DISCORD_CLIENT_SECRET",
            get_env_str("DISCORD_CLIENT_SECRET", ""),
        ),
        "BOT_OPS_DISCORD_REDIRECT_URI": get_env_str(
            "OMO_DISCORD_REDIRECT_URI",
            get_env_str("DISCORD_REDIRECT_URI", ""),
        ),
        "BOT_OPS_ALLOWED_USER_IDS": get_env_tuple("OMO_BOT_OPS_ALLOWED_USER_IDS"),
        "BOT_OPS_DEFAULT_SCOPES": get_env_tuple("OMO_BOT_OPS_DEFAULT_SCOPES", ("ops.read",)),
        "BOT_OPS_SESSION_IDLE_MINUTES": get_env_int("OMO_BOT_OPS_SESSION_IDLE_MINUTES", 60),
    }


# Bot API config values
def get_bot_api_config_values() -> dict:
    """Get bot API-specific configuration values from environment."""
    return {
        "DATABASE_URL": get_env_str(
            "OMO_DATABASE_URL",
            get_env_str("DATABASE_URL",
                        "postgresql://user:password@localhost/omo"),
        ),
        "SECRET_KEY": get_env_str("SECRET_KEY", "dev-secret-key-change-in-production"),
        "DISCORD_TOKEN": get_env_str(
            "OMO_DISCORD_TOKEN",
            get_env_str("DISCORD_TOKEN", ""),
        ),
        "DISCORD_GUILD_ID": get_env_int("OMO_DISCORD_GUILD_ID", 0) or None,
        "SYNDICATION_SOURCES": get_env_tuple("OMO_SYNDICATION_SOURCES"),
        "SYNDICATION_POLL_SECONDS": get_env_int("OMO_SYNDICATION_POLL_SECONDS", 300),
        "LOG_LEVEL": get_env_str("OMO_LOG_LEVEL", "INFO"),
    }
