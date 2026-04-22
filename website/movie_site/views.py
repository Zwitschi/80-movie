from flask import Blueprint, current_app, redirect, render_template, url_for

from .movie_data import get_movie_page_context
from .schema import build_movie_schema_json, build_org_social_schema_json


main_blueprint = Blueprint('main', __name__)


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
    page_context['meta_keywords'] = ', '.join(metadata.get('keywords', movie.get('keywords', [])))
    page_context['meta_image'] = movie['poster_image']
    page_context['meta_url'] = f"{site_url}{metadata['path']}"
    page_context['organization_social_schema_json'] = build_org_social_schema_json(
        movie)
    page_context['movie_schema_json'] = build_movie_schema_json(movie)

    return page_context


@main_blueprint.get('/')
def index():
    return render_template(
        'overview.html',
        **build_page_context('index'),
    )


@main_blueprint.get('/film')
def film():
    return render_template(
        'index.html',
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
