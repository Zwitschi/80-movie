from werkzeug.security import generate_password_hash
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class DefaultConfig:
    SITE_NAME = 'Open Mic Odyssey'
    SITE_URL = os.getenv('SITE_URL', 'https://www.openmicodyssey.com')
    DATABASE_URL = os.getenv(
        'DATABASE_URL', 'postgresql://user:password@localhost/omo')
    DATA_SOURCE = os.getenv('DATA_SOURCE', 'DB')  # 'JSON' or 'DB'
    CURRENT_YEAR = int(
        os.getenv('CURRENT_YEAR', str(datetime.now(timezone.utc).year)))
    MAPBOX_ACCESS_TOKEN = os.getenv('MAPBOX_ACCESS_TOKEN', '')
    SCHEMA_ORG_VERSION_URL = 'https://schema.org/docs/releases.html#v30.0'
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    # Default password is "admin", overridden by env var ADMIN_PASSWORD_HASH
    ADMIN_PASSWORD_HASH = os.getenv(
        'ADMIN_PASSWORD_HASH',
        generate_password_hash('admin')
    )
    BOT_OPS_DISCORD_CLIENT_ID = os.getenv(
        'OMO_DISCORD_CLIENT_ID',
        os.getenv('DISCORD_CLIENT_ID', ''),
    )
    BOT_OPS_DISCORD_CLIENT_SECRET = os.getenv(
        'OMO_DISCORD_CLIENT_SECRET',
        os.getenv('DISCORD_CLIENT_SECRET', ''),
    )
    BOT_OPS_DISCORD_REDIRECT_URI = os.getenv(
        'OMO_DISCORD_REDIRECT_URI',
        os.getenv('DISCORD_REDIRECT_URI', ''),
    )
    BOT_OPS_ALLOWED_USER_IDS = tuple(
        value.strip()
        for value in os.getenv('OMO_BOT_OPS_ALLOWED_USER_IDS', '').split(',')
        if value.strip()
    )
    BOT_OPS_DEFAULT_SCOPES = tuple(
        value.strip()
        for value in os.getenv('OMO_BOT_OPS_DEFAULT_SCOPES', 'ops.read').split(',')
        if value.strip()
    )
    BOT_OPS_SESSION_IDLE_MINUTES = int(
        os.getenv('OMO_BOT_OPS_SESSION_IDLE_MINUTES', '60'))
