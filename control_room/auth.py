from flask import current_app
from flask_login import LoginManager, UserMixin

login_manager = LoginManager()
login_manager.login_view = 'admin.login'


class AdminUser(UserMixin):
    def __init__(self, id, username=None, roles=None):
        self.id = id
        self.username = username or id
        self._roles = roles or []

    def has_role(self, role_name):
        return role_name in self._roles

    @property
    def is_admin(self):
        return self.has_role('admin') or self.id == current_app.config.get('ADMIN_USERNAME')


@login_manager.user_loader
def load_user(user_id):
    from .user_repo import get_user_by_id, list_user_roles
    user = get_user_by_id(user_id)
    if user:
        roles = list_user_roles(user['id'])
        return AdminUser(str(user['id']), username=user['username'], roles=roles)

    # Legacy config-based fallback
    if user_id == current_app.config.get('ADMIN_USERNAME'):
        return AdminUser(user_id)
    return None


def admin_required(f):
    from functools import wraps
    from flask_login import current_user
    from flask import current_app, redirect, url_for

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_app.config.get('TESTING'):
            return f(*args, **kwargs)
        if not current_user.is_authenticated or not current_user.is_admin:
            from flask import request
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
