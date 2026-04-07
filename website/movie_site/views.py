from flask import Blueprint, current_app, render_template

from .movie_data import get_movie_page_context
from .schema import build_movie_schema_json


main_blueprint = Blueprint('main', __name__)


def build_page_context():
    page_context = get_movie_page_context(current_app.config['CURRENT_YEAR'])
    page_context['movie_schema_json'] = build_movie_schema_json(
        page_context['movie'])
    return page_context


@main_blueprint.get('/')
def index():
    return render_template(
        'overview.html',
        **build_page_context(),
    )


@main_blueprint.get('/film')
def film():
    return render_template(
        'index.html',
        **build_page_context(),
    )


@main_blueprint.get('/watch')
def watch():
    return render_template(
        'watch.html',
        **build_page_context(),
    )


@main_blueprint.get('/support')
def support():
    return render_template(
        'support.html',
        **build_page_context(),
    )


@main_blueprint.get('/gallery')
def gallery():
    return render_template(
        'gallery.html',
        **build_page_context(),
    )


@main_blueprint.get('/patreon')
def patreon():
    return render_template(
        'patreon.html',
        **build_page_context(),
    )


@main_blueprint.get('/credits')
def credits():
    return render_template(
        'credits.html',
        **build_page_context(),
    )
