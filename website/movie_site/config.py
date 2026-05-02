import os
from datetime import datetime, timezone


class DefaultConfig:
    SITE_NAME = 'Open Mic Odyssey'
    SITE_URL = os.getenv('SITE_URL', 'https://openmicodyssey.com')
    CURRENT_YEAR = int(
        os.getenv('CURRENT_YEAR', str(datetime.now(timezone.utc).year)))
    MAPBOX_ACCESS_TOKEN = os.getenv('MAPBOX_ACCESS_TOKEN', '')
    SCHEMA_ORG_VERSION_URL = 'https://schema.org/docs/releases.html#v30.0'
