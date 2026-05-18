from werkzeug.security import generate_password_hash
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE_PATH = Path(__file__).parent.parent / ".env"


def _load_website_dotenv() -> None:
    load_dotenv(ENV_FILE_PATH, override=False)


def _env_config_values() -> dict[str, object]:
    current_year = int(
        os.getenv('CURRENT_YEAR', str(datetime.now(timezone.utc).year)))
    return {
        'SITE_URL': os.getenv('SITE_URL', 'https://www.openmicodyssey.com'),
        'DATABASE_URL': os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/omo'),
        'DATA_SOURCE': os.getenv('DATA_SOURCE', 'DB'),
        'CURRENT_YEAR': current_year,
        'MAPBOX_ACCESS_TOKEN': os.getenv('MAPBOX_ACCESS_TOKEN', ''),
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
        'ADMIN_USERNAME': os.getenv('ADMIN_USERNAME', 'admin'),
        'ADMIN_PASSWORD_HASH': os.getenv(
            'ADMIN_PASSWORD_HASH',
            generate_password_hash('admin')
        ),
        'BOT_OPS_DISCORD_CLIENT_ID': os.getenv(
            'OMO_DISCORD_CLIENT_ID',
            os.getenv('DISCORD_CLIENT_ID', ''),
        ),
        'BOT_OPS_DISCORD_CLIENT_SECRET': os.getenv(
            'OMO_DISCORD_CLIENT_SECRET',
            os.getenv('DISCORD_CLIENT_SECRET', ''),
        ),
        'BOT_OPS_DISCORD_REDIRECT_URI': os.getenv(
            'OMO_DISCORD_REDIRECT_URI',
            os.getenv('DISCORD_REDIRECT_URI', ''),
        ),
        'BOT_OPS_ALLOWED_USER_IDS': tuple(
            value.strip()
            for value in os.getenv('OMO_BOT_OPS_ALLOWED_USER_IDS', '').split(',')
            if value.strip()
        ),
        'BOT_OPS_DEFAULT_SCOPES': tuple(
            value.strip()
            for value in os.getenv('OMO_BOT_OPS_DEFAULT_SCOPES', 'ops.read').split(',')
            if value.strip()
        ),
        'BOT_OPS_SESSION_IDLE_MINUTES': int(
            os.getenv('OMO_BOT_OPS_SESSION_IDLE_MINUTES', '60')
        ),
    }


def apply_runtime_env_overrides(app_config) -> None:
    _load_website_dotenv()
    app_config.update(_env_config_values())


_load_website_dotenv()
_DEFAULT_ENV_VALUES = _env_config_values()


class DefaultConfig:
    SITE_NAME = 'Open Mic Odyssey'
    SITE_URL = _DEFAULT_ENV_VALUES['SITE_URL']
    DATABASE_URL = _DEFAULT_ENV_VALUES['DATABASE_URL']
    DATA_SOURCE = _DEFAULT_ENV_VALUES['DATA_SOURCE']  # 'JSON' or 'DB'
    CURRENT_YEAR = _DEFAULT_ENV_VALUES['CURRENT_YEAR']
    MAPBOX_ACCESS_TOKEN = _DEFAULT_ENV_VALUES['MAPBOX_ACCESS_TOKEN']
    SCHEMA_ORG_VERSION_URL = 'https://schema.org/docs/releases.html#v30.0'
    SECRET_KEY = _DEFAULT_ENV_VALUES['SECRET_KEY']
    ADMIN_USERNAME = _DEFAULT_ENV_VALUES['ADMIN_USERNAME']
    # Default password is "admin", overridden by env var ADMIN_PASSWORD_HASH
    ADMIN_PASSWORD_HASH = _DEFAULT_ENV_VALUES['ADMIN_PASSWORD_HASH']
    BOT_OPS_DISCORD_CLIENT_ID = _DEFAULT_ENV_VALUES['BOT_OPS_DISCORD_CLIENT_ID']
    BOT_OPS_DISCORD_CLIENT_SECRET = _DEFAULT_ENV_VALUES['BOT_OPS_DISCORD_CLIENT_SECRET']
    BOT_OPS_DISCORD_REDIRECT_URI = _DEFAULT_ENV_VALUES['BOT_OPS_DISCORD_REDIRECT_URI']
    BOT_OPS_ALLOWED_USER_IDS = _DEFAULT_ENV_VALUES['BOT_OPS_ALLOWED_USER_IDS']
    BOT_OPS_DEFAULT_SCOPES = _DEFAULT_ENV_VALUES['BOT_OPS_DEFAULT_SCOPES']
    BOT_OPS_SESSION_IDLE_MINUTES = _DEFAULT_ENV_VALUES['BOT_OPS_SESSION_IDLE_MINUTES']
