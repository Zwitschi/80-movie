from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from .content_common import _ctx
from .content_connect import (
    _handle_connect_patreon_request,
    _handle_connect_request,
    _handle_connect_social_request,
    _handle_connect_supporters_request,
)
from .content_events import _handle_events_request
from .content_faq import _handle_faq_request
from .content_film import _handle_film_request
from .content_media import _handle_media_request
from .content_media_assets import _handle_media_assets_request
from .content_pages import _handle_content_request
from .content_people import _handle_people_request
from .content_reviews import _handle_reviews_request

content_blueprint = Blueprint(
    'content', __name__, url_prefix='/content', static_folder='static')


@content_blueprint.before_request
def require_login():
    if current_app.config.get('TESTING'):
        return None

    if not current_user.is_authenticated:
        return redirect(url_for('admin.login', next=request.url))


@content_blueprint.get('/')
def dashboard():
    return render_template('admin.html', **_ctx())


@content_blueprint.route('/film', methods=['GET', 'POST'])
def edit_film():
    return _handle_film_request(request)


@content_blueprint.route('/media', methods=['GET', 'POST'])
def manage_media():
    return _handle_media_request(request)


@content_blueprint.route('/content', methods=['GET', 'POST'])
def edit_content():
    return _handle_content_request(request)


@content_blueprint.route('/events', methods=['GET', 'POST'])
def edit_events():
    return _handle_events_request(request)


@content_blueprint.route('/faq', methods=['GET', 'POST'])
def edit_faq():
    return _handle_faq_request(request)


@content_blueprint.route('/people', methods=['GET', 'POST'])
def edit_people():
    return _handle_people_request(request)


@content_blueprint.route('/connect', methods=['GET', 'POST'])
def edit_connect():
    return _handle_connect_request(request)


@content_blueprint.route('/connect/social', methods=['GET', 'POST'])
def edit_connect_social():
    return _handle_connect_social_request(request)


@content_blueprint.route('/connect/supporters', methods=['GET', 'POST'])
def edit_connect_supporters():
    return _handle_connect_supporters_request(request)


@content_blueprint.route('/connect/patreon', methods=['GET', 'POST'])
def edit_connect_patreon():
    return _handle_connect_patreon_request(request)


@content_blueprint.route('/media-assets', methods=['GET', 'POST'])
def edit_media_assets():
    return _handle_media_assets_request(request)


@content_blueprint.route('/reviews', methods=['GET', 'POST'])
def edit_reviews():
    return _handle_reviews_request(request)


@content_blueprint.get('/submissions')
def view_submissions():
    return render_template('view_submissions.html', **_ctx())
