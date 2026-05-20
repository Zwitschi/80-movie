import os
from pathlib import Path
from flask import Flask

from shared.db import init_app as init_db_app
from shared.config import load_dotenv_files, get_website_config_values
from .views import main_blueprint


def create_app():
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )

    # Load env files
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv_files(repo_root / ".env", repo_root / "website" / ".env")

    # Apply config
    app.config.update(get_website_config_values())

    init_db_app(app)

    app.register_blueprint(main_blueprint)
    return app
