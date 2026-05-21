from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash

from .auth import AdminUser
from .admin_content import _ctx

admin_blueprint = Blueprint(
    'admin', __name__, url_prefix='/', static_folder='static')


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

        # Try database auth first
        from .user_repo import get_user_by_username, verify_password
        user_record = get_user_by_username(username)
        if user_record and verify_password(user_record['password_hash'], password):
            user = AdminUser(
                str(user_record['id']), username=user_record['username'])
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.dashboard'))

        # Legacy config-based fallback
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

        error = 'Invalid credentials'

    return render_template('admin/login.html', error=error)


@admin_blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('admin.login'))


@admin_blueprint.get('/')
def dashboard():
    return render_template('admin/admin.html', **_ctx())
