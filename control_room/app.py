"""Control room Flask application.

Standalone Flask app for admin CMS, bot operator login, health/config views,
and syndication control APIs.
"""

import os
from shared.db import init_app as init_db_app
from shared.config import load_dotenv_files, get_control_room_config_values
from flask_login import LoginManager
from flask import Flask


def create_app() -> Flask:
    """Create and configure the control room Flask application."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]

    # Load env files
    load_dotenv_files(repo_root / ".env", repo_root / ".env.control_room")

    # Resolve template folder from control_room package
    control_room_templates = str(Path(__file__).parent / "templates")
    website_static = str(repo_root / "website" / "static")

    app = Flask(
        __name__,
        template_folder=control_room_templates,
        static_folder=website_static,
    )

    # Apply config
    app.config.update(get_control_room_config_values())

    # Initialize DB
    init_db_app(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'admin.login'

    @login_manager.user_loader
    def load_user(user_id):
        from .auth import load_user as load_admin_user
        return load_admin_user(user_id)

    # Register auth + dashboard blueprint
    from .admin import admin_blueprint
    app.register_blueprint(admin_blueprint)

    # Register content management blueprint
    from .content import content_blueprint
    app.register_blueprint(content_blueprint)

    # Seed default admin user if table exists and empty
    with app.app_context():
        try:
            from flask import current_app as _current_app
            from .user_repo import seed_default_admin
            admin_user = _current_app.config.get('ADMIN_USERNAME')
            admin_pass = _current_app.config.get('ADMIN_PASSWORD')
            admin_hash = _current_app.config.get('ADMIN_PASSWORD_HASH')
            if admin_user and (admin_pass or admin_hash):
                seed_default_admin(
                    admin_user,
                    config_password=admin_pass,
                    config_password_hash=admin_hash,
                )
        except Exception:
            pass

    return app


# Module-level app instance for gunicorn (lazy creation)
_app_instance = None


def get_app():
    """Get or create the Flask app instance."""
    global _app_instance
    if _app_instance is None:
        _app_instance = create_app()
    return _app_instance


# Only auto-create for gunicorn (not during test imports)
if os.environ.get('CONTROL_ROOM_AUTO_CREATE', '1') == '1':
    app = get_app()
