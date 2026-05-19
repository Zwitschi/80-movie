"""Control room Flask application.

Standalone Flask app for admin CMS, bot operator login, health/config views,
and syndication control APIs.
"""

from pathlib import Path
import sys

# Ensure website is on sys.path before any imports
repo_root = Path(__file__).resolve().parents[1]
website_path = str(repo_root / "website")
if website_path not in sys.path:
    sys.path.insert(0, website_path)

from flask import Flask
from flask_login import LoginManager

from shared.config import load_dotenv_files, get_control_room_config_values
from shared.db import init_app as init_db_app


def create_app() -> Flask:
    """Create and configure the control room Flask application."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]

    # Load env files
    load_dotenv_files(repo_root / ".env", repo_root / "website" / ".env")

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
        from .auth import AdminUser
        return AdminUser(user_id)

    # Register admin CMS blueprint
    from .admin import admin_blueprint
    app.register_blueprint(admin_blueprint)

    # Register bot operator blueprint
    from movie_site.admin_bot import admin_bot_blueprint, oauth_callback
    app.register_blueprint(admin_bot_blueprint)
    app.add_url_rule(
        '/oauth/discord/callback',
        endpoint='discord_oauth_callback',
        view_func=oauth_callback,
        methods=['GET'],
    )

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
import os
if os.environ.get('CONTROL_ROOM_AUTO_CREATE', '1') == '1':
    app = get_app()
