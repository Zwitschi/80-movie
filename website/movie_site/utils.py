"""Utility functions for website.

Website-specific helpers (_ctx) live here. Shared helpers come from shared.utils.
"""

from flask import current_app
from shared.utils import (
    get_admin_reader,
    get_admin_writer,
    load_json,
    save_json,
    _coerce_release_status,
    _movie_form_fields,
    _gallery_form_fields,
    _content_page_form_fields,
    _validate_content_pages,
    _build_content_previews,
    process_list_action,
    _validate_iso_datetime,
    _validate_iso_date,
    _validate_schema_org_url,
    EVENT_STATUSES,
    EVENT_ATTENDANCE_MODES,
    OFFER_AVAILABILITIES,
)


def _ctx():
    """Build page context for admin templates. Website-specific."""
    from .movie_data import get_movie_page_context
    return get_movie_page_context(current_app.config['CURRENT_YEAR'])


__all__ = [
    '_ctx',
    'get_admin_reader',
    'get_admin_writer',
    'load_json',
    'save_json',
    '_coerce_release_status',
    '_movie_form_fields',
    '_gallery_form_fields',
    '_content_page_form_fields',
    '_validate_content_pages',
    '_build_content_previews',
    'process_list_action',
    '_validate_iso_datetime',
    '_validate_iso_date',
    '_validate_schema_org_url',
    'EVENT_STATUSES',
    'EVENT_ATTENDANCE_MODES',
    'OFFER_AVAILABILITIES',
]
