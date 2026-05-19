"""Control room Flask application.

Standalone Flask app for bot operator login, health/config views,
and syndication control APIs. Currently wraps the embedded admin_bot blueprint
from website/movie_site for backward compatibility.
"""

from flask import Flask

from shared.config import load_dotenv_files, get_control_room_config_values
from shared.db import init_app as init_db_app


def create_app() -> Flask:
    """Create and configure the control room Flask application."""
    app = Flask(__name__)

    # Load env files
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv_files(repo_root / ".env", repo_root / "website" / ".env")

    # Apply config
    app.config.update(get_control_room_config_values())

    # Initialize DB
    init_db_app(app)

    # Import and register admin_bot blueprint from website
    # This will be replaced with native control_room blueprints in Phase 2
    import sys
    website_path = str(repo_root / "website")
    if website_path not in sys.path:
        sys.path.insert(0, website_path)

    from movie_site.admin_bot import admin_bot_blueprint, oauth_callback

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
