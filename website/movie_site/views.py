from urllib.parse import urlparse
from xml.sax.saxutils import escape

from flask import Blueprint, current_app, redirect, render_template, url_for

from .movie_data import get_movie_data, get_movie_page_context
from .schema import build_movie_schema_json, build_org_social_schema_json


main_blueprint = Blueprint('main', __name__)
ROBOTS_ALLOW = 'User-agent: *\nAllow: /\n'
SITEMAP_PAGE_PATHS = ('/', '/film', '/media', '/connect',
                      '/patreon', '/watch', '/credits')


PAGE_METADATA = {
    'index': {
        'title': 'Overview',
        'description': 'Watch the trailer and follow the latest release updates for Open Mic Odyssey.',
        'keywords': [
            'open mic odyssey documentary',
            'comedy road trip documentary',
            'independent documentary trailer',
            'stand-up comedy film',
            'documentary film updates',
        ],
        'path': '/',
    },
    'film': {
        'title': 'Film',
        'description': 'Read the synopsis, credits, and screening access details for Open Mic Odyssey.',
        'keywords': [
            'documentary film synopsis',
            'independent documentary credits',
            'comedy documentary cast',
            'open mic odyssey screenings',
            'road trip documentary story',
        ],
        'path': '/film',
    },
    'media': {
        'title': 'Media',
        'description': 'Browse stills, poster art, and behind-the-scenes images from Open Mic Odyssey.',
        'keywords': [
            'documentary behind the scenes photos',
            'film stills and poster art',
            'open mic odyssey media kit',
            'independent film gallery',
            'comedy documentary images',
        ],
        'path': '/media',
    },
    'connect': {
        'title': 'Connect',
        'description': 'Follow Open Mic Odyssey across official channels and support updates.',
        'keywords': [
            'follow open mic odyssey',
            'documentary social channels',
            'film release updates',
            'independent film community',
            'comedy documentary news',
        ],
        'path': '/connect',
    },
    'patreon': {
        'title': 'Supporters',
        'description': 'Explore supporter benefits, membership tiers, and Patreon access for Open Mic Odyssey.',
        'keywords': [
            'patreon documentary support',
            'support independent documentary',
            'film membership tiers',
            'bonus documentary content',
            'open mic odyssey patreon',
        ],
        'path': '/patreon',
    },
}


def build_page_context(page_key='index'):
    page_context = get_movie_page_context(current_app.config['CURRENT_YEAR'])
    movie = page_context['movie']
    site_url = current_app.config['SITE_URL'].rstrip('/')
    metadata = PAGE_METADATA.get(page_key, PAGE_METADATA['index'])

    page_context['meta_title'] = f"{metadata['title']} | {movie['title']}"
    page_context['meta_description'] = metadata['description'] or movie['description']
    page_context['meta_keywords'] = ', '.join(
        metadata.get('keywords', movie.get('keywords', [])))
    page_context['meta_image'] = movie['poster_image']
    page_context['meta_url'] = f"{site_url}{metadata['path']}"
    page_context['organization_social_schema_json'] = build_org_social_schema_json(
        movie)
    page_context['movie_schema_json'] = build_movie_schema_json(movie)

    return page_context


def iter_static_asset_paths(value):
    if isinstance(value, dict):
        for nested_value in value.values():
            yield from iter_static_asset_paths(nested_value)
        return

    if isinstance(value, list):
        for nested_value in value:
            yield from iter_static_asset_paths(nested_value)
        return

    if not isinstance(value, str):
        return

    parsed = urlparse(value)
    if parsed.path.startswith('/static/'):
        yield parsed.path
    elif value.startswith('/static/'):
        yield value


def build_sitemap_xml() -> str:
    site_url = current_app.config['SITE_URL'].rstrip('/')
    movie_data = get_movie_data()

    locations = [f'{site_url}{path}' for path in SITEMAP_PAGE_PATHS]
    static_asset_paths = sorted(set(iter_static_asset_paths(movie_data)))
    locations.extend(f'{site_url}{path}' for path in static_asset_paths)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for location in locations:
        lines.append('  <url>')
        lines.append(f'    <loc>{escape(location)}</loc>')
        lines.append('  </url>')
    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'


@main_blueprint.get('/')
def index():
    return render_template(
        'index.html',
        **build_page_context('index'),
    )


@main_blueprint.get('/film')
def film():
    return render_template(
        'film.html',
        **build_page_context('film'),
    )


@main_blueprint.get('/watch')
def watch():
    return redirect(url_for('main.index', _anchor='trailer'))


@main_blueprint.get('/connect')
def connect():
    return render_template(
        'connect.html',
        **build_page_context('connect'),
    )


@main_blueprint.get('/support')
def support():
    return redirect(url_for('main.connect'))


@main_blueprint.get('/media')
def media():
    return render_template(
        'media.html',
        **build_page_context('media'),
    )


@main_blueprint.get('/gallery')
def gallery():
    return redirect(url_for('main.media'))


@main_blueprint.get('/patreon')
def patreon():
    return render_template(
        'patreon.html',
        **build_page_context('patreon'),
    )


@main_blueprint.get('/credits')
def credits():
    return redirect(url_for('main.film', _anchor='credits'))


@main_blueprint.get('/robots.txt')
def robots_txt():
    return current_app.response_class(
        ROBOTS_ALLOW,
        mimetype='text/plain',
    )


@main_blueprint.get('/sitemap.xml')
def sitemap_xml():
    return current_app.response_class(
        build_sitemap_xml(),
        mimetype='application/xml',
    )
