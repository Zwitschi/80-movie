from flask import Flask

from .config import DefaultConfig, apply_runtime_env_overrides
from .db import init_app as init_db_app
from .views import main_blueprint


def create_app(config_object=DefaultConfig):
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )
    app.config.from_object(config_object)
    apply_runtime_env_overrides(app.config)

    init_db_app(app)

    app.register_blueprint(main_blueprint)
    return app
