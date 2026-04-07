from flask import Flask

from .config import DefaultConfig
from .views import main_blueprint


def create_app(config_object=DefaultConfig):
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )
    app.config.from_object(config_object)
    app.register_blueprint(main_blueprint)
    return app
