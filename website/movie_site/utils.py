import sys
from flask import current_app
from .content_store import ContentReadError, ContentWriteError


def _ctx():
    from .movie_data import get_movie_page_context
    return get_movie_page_context(current_app.config['CURRENT_YEAR'])


def get_admin_reader():
    from .content_store import get_content_reader
    return get_content_reader()


def get_admin_writer():
    from .content_store import get_content_writer
    return get_content_writer()


def load_json(filename: str, default_val=None):
    if default_val is None:
        default_val = {}
    try:
        from .content_store import get_content_reader
        return get_content_reader().read(filename)
    except ContentReadError:
        return default_val


def save_json(filename: str, payload: dict) -> tuple[bool, str | None]:
    try:
        from .content_store import get_content_writer
        get_content_writer().write(filename, payload)
        return True, None
    except ContentWriteError as exc:
        return False, str(exc)


def _coerce_release_status(movie_payload: dict) -> dict:
    release_status = movie_payload.get('release_status')
    if isinstance(release_status, dict):
        return release_status
    return {
        'label': '',
        'headline': '',
        'summary': '',
        'detail': '',
    }


def _movie_form_fields(movie_payload: dict) -> dict:
    release_status = _coerce_release_status(movie_payload)
    return {
        'title': movie_payload.get('title', ''),
        'tagline': movie_payload.get('tagline', ''),
        'description': movie_payload.get('description', ''),
        'genre': movie_payload.get('genre', ''),
        'runtime': movie_payload.get('runtime', ''),
        'duration_iso': movie_payload.get('duration_iso', ''),
        'release_date': movie_payload.get('release_date', ''),
        'release_status_label': release_status.get('label', ''),
        'release_status_headline': release_status.get('headline', ''),
        'release_status_summary': release_status.get('summary', ''),
        'release_status_detail': release_status.get('detail', ''),
    }


def _gallery_form_fields(item_payload: dict | None = None) -> dict:
    item_payload = item_payload or {}
    return {
        'title': item_payload.get('title', ''),
        'category': item_payload.get('category', ''),
        'image_url': item_payload.get('image_url', ''),
        'alt': item_payload.get('alt', ''),
        'description': item_payload.get('description', ''),
    }


def _content_page_form_fields(page_payload: dict | None = None) -> dict:
    page_payload = page_payload or {}
    keywords = page_payload.get('keywords', [])
    if not isinstance(keywords, list):
        keywords = []
    return {
        'title': page_payload.get('title', ''),
        'description': page_payload.get('description', ''),
        'keywords': ', '.join(keywords),
        'path': page_payload.get('path', ''),
    }


def _validate_content_pages(pages_payload: dict, required_keys: tuple) -> str | None:
    missing_keys = [key for key in required_keys if key not in pages_payload]
    if missing_keys:
        return f"Missing required page keys: {', '.join(missing_keys)}"

    for key in required_keys:
        page = pages_payload.get(key, {})
        if not isinstance(page, dict):
            return f'Invalid page object for key: {key}'
        for required_field in ('title', 'description', 'path'):
            value = page.get(required_field, '')
            if not isinstance(value, str) or not value.strip():
                return f'Missing required value: {key}.{required_field}'

    return None


def _build_content_previews(pages_payload: dict, movie_title: str) -> list[dict]:
    previews = []
    for key in sorted(pages_payload.keys()):
        page = pages_payload.get(key, {})
        title = page.get('title', '')
        description = page.get('description', '')
        previews.append(
            {
                'key': key,
                'title': title,
                'description': description,
                'generated_title': f'{title} | {movie_title}'.strip(),
            }
        )
    return previews


def process_list_action(items: list, action: str, index_str: str, candidate: dict | None = None) -> list:
    updated = list(items)
    try:
        idx = int(index_str) if index_str else -1
    except ValueError:
        idx = -1

    if action == 'remove' and 0 <= idx < len(updated):
        updated.pop(idx)
    elif action == 'move_up' and 1 <= idx < len(updated):
        updated[idx - 1], updated[idx] = updated[idx], updated[idx - 1]
    elif action == 'move_down' and 0 <= idx < len(updated) - 1:
        updated[idx], updated[idx + 1] = updated[idx + 1], updated[idx]
    elif action == 'add' and candidate is not None:
        updated.append(candidate)

    return updated


print('test', file=sys.stderr)
print('test utils', file=sys.stderr)
