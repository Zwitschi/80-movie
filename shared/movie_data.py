"""Shared movie data helpers.

Contains pure functions and data aggregators that don't depend on Flask app context directly
(but may accept a flask_app object for content reading).
"""

from urllib.parse import urlparse

from .content_store import get_content_reader

PRODUCTION_COMPANY_NAME = 'Open Mic Odyssey Productions'


def get_movie_data(flask_app=None):
    """Aggregates content records into page-ready data model."""
    reader = get_content_reader(flask_app)
    all_data = reader.read_all()

    organizations = all_data.get(
        'organizations', {}).get('organizations', {})
    connect_payload = all_data.get('connect', {}).get('connect', {})
    connect_page = connect_payload.get('page', {})
    if not isinstance(connect_page, dict):
        connect_page = {}
    connect_page.setdefault('primary_link', {'label': '', 'url': ''})
    connect_page.setdefault('secondary_link', {'label': '', 'url': ''})
    connect_page.setdefault('benefits', [])
    connect_page.setdefault('tiers', [])
    production_company = organizations.get(PRODUCTION_COMPANY_NAME, {})

    people = all_data.get('people', {}).get('people', {})
    if not isinstance(people, dict):
        people = {}
    credits_people = all_data.get('people', {}).get('credits_people', [])
    if not isinstance(credits_people, list):
        credits_people = []
    cast_people = _build_cast_people(credits_people, people)
    social_links = all_data.get('social', {}).get('social', [])
    if not isinstance(social_links, list):
        social_links = []
    social_gallery_items = _build_social_gallery_items(social_links)
    social_gallery_embed_items = [
        item for item in social_gallery_items if item.get('embed_url')
    ]
    social_gallery_profile_items = [
        item for item in social_gallery_items if not item.get('embed_url')
    ]

    return {
        **all_data.get('movies', {}).get('movie', {}),
        **all_data.get('media_assets', {}).get('media', {}),
        **all_data.get('reviews', {}),
        **all_data.get('offers', {}),
        'people': people,
        'contributors': all_data.get('people', {}).get('contributors', {}),
        'credits_people': credits_people,
        'cast_people': cast_people,
        'cast_section_visible': any(entry['description'] for entry in cast_people),
        'organizations': organizations,
        'production_company': production_company,
        'screenings': all_data.get('events', {}).get('events', []),
        'faq_items': all_data.get('faq', {}).get('faq', []),
        'gallery_items': all_data.get('gallery', {}).get('gallery', []),
        'social_links': social_links,
        'social_gallery_items': social_gallery_items,
        'social_gallery_embed_items': social_gallery_embed_items,
        'social_gallery_profile_items': social_gallery_profile_items,
        'connect_links': connect_payload.get('links', {}),
        'connect_page': connect_page,
        'page_metadata': all_data.get('content', {}).get('pages', {}),
    }


def get_movie_page_context(current_year, flask_app=None):
    """Builds basic page context including movie data."""
    movie = get_movie_data(flask_app)
    return {
        'movie': movie,
        'movie_title': movie['title'],
        'movie_tagline': movie['tagline'],
        'movie_description': movie['description'],
        'movie_genre': movie['genre'],
        'movie_runtime': movie['runtime'],
        'release_date': movie['release_date'],
        'release_status': movie['release_status'],
        'current_year': current_year,
    }


def _build_cast_people(
    credits_people: list[dict[str, object]],
    people: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    cast_entries: list[dict[str, object]] = []
    cast_by_name: dict[str, dict[str, object]] = {}

    for credit in credits_people:
        if not isinstance(credit, dict):
            continue

        name = str(credit.get('name') or '').strip()
        if not name:
            continue

        role = str(credit.get('role') or '').strip()
        person = people.get(name, {}) if isinstance(people, dict) else {}
        description = str(person.get('credit_note') or '').strip()

        entry = cast_by_name.get(name)
        if entry is None:
            entry = {
                'name': name,
                'roles': [],
                'description': description,
            }
            cast_by_name[name] = entry
            cast_entries.append(entry)
        elif not entry['description'] and description:
            entry['description'] = description

        roles = entry['roles'] if isinstance(entry['roles'], list) else []
        if role and role not in roles:
            roles.append(role)
        entry['roles'] = roles

    return cast_entries


def _build_social_gallery_items(social_links: list[dict[str, object]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    for link in social_links:
        if not isinstance(link, dict):
            continue

        label = str(link.get('label') or '').strip()
        url = str(link.get('url') or '').strip()
        description = str(link.get('description') or '').strip()
        platform = _infer_social_platform(label, url)

        if platform not in ('instagram', 'tiktok'):
            continue

        embed_url = _build_social_embed_url(platform, url)
        items.append(
            {
                'platform': platform,
                'label': label or platform.title(),
                'url': url,
                'description': description,
                'embed_url': embed_url,
            }
        )

    return items


def _infer_social_platform(label: str, url: str) -> str:
    label_lower = label.lower()
    if 'instagram' in label_lower:
        return 'instagram'
    if 'tiktok' in label_lower:
        return 'tiktok'

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if 'instagram.com' in host:
        return 'instagram'
    if 'tiktok.com' in host:
        return 'tiktok'

    return ''


def _build_social_embed_url(platform: str, url: str) -> str:
    parsed = urlparse(url)
    segments = [segment for segment in parsed.path.split('/') if segment]
    if not segments:
        return ''

    if platform == 'instagram':
        if len(segments) >= 2 and segments[0] in ('p', 'reel', 'tv'):
            return f'https://www.instagram.com/{segments[0]}/{segments[1]}/embed/captioned/'
        return ''

    if platform == 'tiktok':
        if 'video' in segments:
            video_index = segments.index('video')
            if video_index + 1 < len(segments):
                video_id = segments[video_index + 1]
                if video_id.isdigit():
                    return f'https://www.tiktok.com/embed/v2/{video_id}'
        return ''

    return ''
