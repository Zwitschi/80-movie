"""Control room Flask application.

Standalone Flask app for bot operator login, health/config views,
and syndication control APIs. Currently wraps the embedded admin_bot blueprint
from website/movie_site for backward compatibility.
"""

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

    # Add website to sys.path so movie_site is importable
    website_path = str(repo_root / "website")
    import sys
    if website_path not in sys.path:
        sys.path.insert(0, website_path)

    # Resolve template folder from movie_site package location
    import movie_site
    movie_site_path = Path(movie_site.__file__).parent
    website_templates = str(movie_site_path.parent / "templates")
    website_static = str(movie_site_path.parent / "static")

    app = Flask(
        __name__,
        template_folder=website_templates,
        static_folder=website_static,
    )

    # Apply config
    app.config.update(get_control_room_config_values())

    # Initialize DB
    init_db_app(app)

    # Initialize Flask-Login (required by admin_blueprint)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'admin.login'

    @login_manager.user_loader
    def load_user(user_id):
        from movie_site.auth import AdminUser
        return AdminUser(user_id)

    # Import and register admin_bot blueprint from website
    # This will be replaced with native control_room blueprints in Phase 2
    from movie_site.admin_bot import admin_bot_blueprint, oauth_callback
    from movie_site.admin import admin_blueprint

    app.register_blueprint(admin_blueprint)
    app.register_blueprint(admin_bot_blueprint)
    app.add_url_rule(
        '/oauth/discord/callback',
        endpoint='discord_oauth_callback',
        view_func=oauth_callback,
        methods=['GET'],
    )

    return app


# Module-level app instance for gunicorn
app = create_app()
