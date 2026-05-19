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
