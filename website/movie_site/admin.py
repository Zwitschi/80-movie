from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash

from .admin_content import (
    _handle_film_request,
    _handle_media_request,
    _handle_content_request,
    _handle_events_request,
    _handle_faq_request,
    _handle_people_request,
    _handle_connect_request,
    _handle_media_assets_request,
    _handle_reviews_request,
)
from .auth import AdminUser
from .content_store import ContentReadError, ContentWriteError, get_content_reader, get_content_writer
from .utils import (
    _ctx,
)

admin_blueprint = Blueprint('admin', __name__, url_prefix='/admin')


@admin_blueprint.before_request
def require_login():
    if current_app.config.get('TESTING'):
        return None

    if request.endpoint != 'admin.login' and not current_user.is_authenticated:
        return redirect(url_for('admin.login', next=request.url))


@admin_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        valid_username = current_app.config.get('ADMIN_USERNAME')
        valid_hash = current_app.config.get('ADMIN_PASSWORD_HASH')

        if (
            username == valid_username
            and isinstance(valid_hash, str)
            and check_password_hash(valid_hash, password)
        ):
            user = AdminUser(username)
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.dashboard'))
        else:
            error = 'Invalid credentials'

    return render_template('admin/login.html', error=error)


@admin_blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@admin_blueprint.get('/')
def dashboard():
    return render_template('admin/admin.html', **_ctx())


@admin_blueprint.route('/film', methods=['GET', 'POST'])
def edit_film():
    return _handle_film_request(request)


@admin_blueprint.route('/media', methods=['GET', 'POST'])
def manage_media():
    return _handle_media_request(request)


@admin_blueprint.route('/content', methods=['GET', 'POST'])
def edit_content():
    return _handle_content_request(request)


@admin_blueprint.route('/events', methods=['GET', 'POST'])
def edit_events():
    return _handle_events_request(request)


@admin_blueprint.route('/faq', methods=['GET', 'POST'])
def edit_faq():
    return _handle_faq_request(request)


@admin_blueprint.route('/people', methods=['GET', 'POST'])
def edit_people():
    return _handle_people_request(request)


@admin_blueprint.route('/connect', methods=['GET', 'POST'])
def edit_connect():
    return _handle_connect_request(request)


@admin_blueprint.route('/media-assets', methods=['GET', 'POST'])
def edit_media_assets():
    return _handle_media_assets_request(request)


@admin_blueprint.route('/reviews', methods=['GET', 'POST'])
def edit_reviews():
    return _handle_reviews_request(request)


@admin_blueprint.get('/submissions')
def view_submissions():
    return render_template('admin/view_submissions.html', **_ctx())
