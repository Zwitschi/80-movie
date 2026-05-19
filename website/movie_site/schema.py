"""Schema.org JSON-LD generation — delegates to shared.schema."""

from shared.schema import (
    build_movie_schema_json,
    build_org_social_schema_json,
)

__all__ = [
    'build_movie_schema_json',
    'build_org_social_schema_json',
]
