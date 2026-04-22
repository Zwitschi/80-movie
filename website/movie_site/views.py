from flask import Blueprint, current_app, redirect, render_template, url_for

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
    return redirect(url_for('main.index', _anchor='trailer'))


@main_blueprint.get('/connect')
def connect():
    return render_template(
        'connect.html',
        **build_page_context(),
    )


@main_blueprint.get('/support')
def support():
    return redirect(url_for('main.connect'))


@main_blueprint.get('/media')
def media():
    return render_template(
        'media.html',
        **build_page_context(),
    )


@main_blueprint.get('/gallery')
def gallery():
    return redirect(url_for('main.media'))


@main_blueprint.get('/patreon')
def patreon():
    return render_template(
        'patreon.html',
        **build_page_context(),
    )


@main_blueprint.get('/credits')
def credits():
    return redirect(url_for('main.film', _anchor='credits'))
