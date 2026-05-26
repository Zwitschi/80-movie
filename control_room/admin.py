from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash
from secrets import compare_digest

from .auth import AdminUser
from .content_common import _ctx

admin_blueprint = Blueprint(
    'admin', __name__, url_prefix='/', static_folder='static')


def _matches_config_password(password: str) -> bool:
    valid_password = current_app.config.get('ADMIN_PASSWORD')
    if isinstance(valid_password, str) and valid_password:
        if compare_digest(valid_password, password):
            return True

    valid_hash = current_app.config.get('ADMIN_PASSWORD_HASH')
    if not isinstance(valid_hash, str) or not valid_hash:
        return False

    try:
        return check_password_hash(valid_hash, password)
    except (TypeError, ValueError):
        return False


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
        if (
            username == valid_username
            and _matches_config_password(password)
        ):
            user = AdminUser(username)
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.dashboard'))

        error = 'Invalid credentials'

    return render_template('login.html', error=error)


@admin_blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('admin.login'))


@admin_blueprint.get('/')
def dashboard():
    return render_template('admin.html', **_ctx())


@admin_blueprint.route('/users', methods=['GET', 'POST'])
def manage_users():
    from .user_repo import list_users, create_user, update_user, delete_user, update_password

    error = None
    success = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'create':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            if username and email and password:
                try:
                    user = create_user(username, email, password)
                    if user:
                        from .user_repo import assign_role
                        assign_role(user['id'], 'admin')
                        success = f"User '{username}' created."
                    else:
                        error = 'Users table not available.'
                except Exception as exc:
                    error = str(exc)
            else:
                error = 'Username, email, and password required.'

        elif action == 'update':
            user_id = request.form.get('user_id', '').strip()
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            is_active = request.form.get('is_active')
            is_active_bool = is_active == '1' if is_active else None
            if user_id:
                try:
                    update_user(
                        user_id,
                        username=username or None,
                        email=email or None,
                        is_active=is_active_bool,
                    )
                    success = 'User updated.'
                except Exception as exc:
                    error = str(exc)
            else:
                error = 'User ID required.'

        elif action == 'delete':
            user_id = request.form.get('user_id', '').strip()
            if user_id:
                try:
                    delete_user(user_id)
                    success = 'User deleted.'
                except Exception as exc:
                    error = str(exc)
            else:
                error = 'User ID required.'

        elif action == 'reset_password':
            user_id = request.form.get('user_id', '').strip()
            new_password = request.form.get('new_password', '').strip()
            if user_id and new_password:
                try:
                    update_password(user_id, new_password)
                    success = 'Password reset.'
                except Exception as exc:
                    error = str(exc)
            else:
                error = 'User ID and new password required.'

    users = list_users()
    return render_template(
        'manage_users.html',
        users=users,
        error=error,
        success=success,
        **_ctx(),
    )


@admin_blueprint.route('/logs', methods=['GET'])
def view_logs():
    from shared.logging_db import query_logs, get_log_count

    service_filter = request.args.get('service', '') or None
    level_filter = request.args.get('level', '') or None
    page = int(request.args.get('page', 1))
    per_page = 50
    offset = (page - 1) * per_page

    logs = query_logs(
        service_name=service_filter,
        log_level=level_filter,
        limit=per_page,
        offset=offset,
    )
    total = get_log_count(
        service_name=service_filter,
        log_level=level_filter,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        'view_logs.html',
        logs=logs,
        service_filter=service_filter,
        level_filter=level_filter,
        page=page,
        total_pages=total_pages,
        **_ctx(),
    )
