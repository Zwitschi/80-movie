"""Bot API Flask application.

Standalone Flask app exposing health, config, and syndication endpoints
for the bot worker runtime.
"""

from flask import Flask, jsonify

from shared.config import load_dotenv_files, get_bot_api_config_values
from shared.db import init_app as init_db_app


def create_app() -> Flask:
    """Create and configure the bot API Flask application."""
    app = Flask(__name__)

    # Load env files
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv_files(repo_root / ".env", repo_root / "website" / ".env")

    # Apply config
    app.config.update(get_bot_api_config_values())

    # Initialize DB
    init_db_app(app)

    # Register health endpoint
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "service": "bot-api",
            "database_configured": bool(app.config.get('DATABASE_URL')),
            "discord_token_configured": bool(app.config.get('DISCORD_TOKEN')),
        })

    # Register config endpoint
    @app.route('/api/config')
    def config_info():
        """Expose non-sensitive bot configuration."""
        return jsonify({
            "guild_id": app.config.get('DISCORD_GUILD_ID'),
            "syndication_sources": app.config.get('SYNDICATION_SOURCES', []),
            "syndication_poll_seconds": app.config.get('SYNDICATION_POLL_SECONDS', 300),
            "log_level": app.config.get('LOG_LEVEL', 'INFO'),
        })

    return app


# Module-level app instance for gunicorn
app = create_app()
