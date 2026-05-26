from pathlib import Path
from flask import Flask

from shared.db import init_app as init_db_app
from shared.config import load_dotenv_files, get_website_config_values
from shared.logging_db import DbLogHandler, set_service_name
from .views import main_blueprint


def create_app():
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )

    # Load env files
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv_files(repo_root / ".env", repo_root / ".env.website")

    # Apply config
    app.config.update(get_website_config_values())

    init_db_app(app)

    # Attach DB logging
    set_service_name('website')
    import logging
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    root_logger.addHandler(DbLogHandler())

    app.register_blueprint(main_blueprint)
    return app
