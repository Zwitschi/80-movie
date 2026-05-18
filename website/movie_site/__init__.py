from flask import Flask

from .admin import admin_blueprint
from .admin_bot import admin_bot_blueprint
from .auth import login_manager
from .config import DefaultConfig
from .db import init_app as init_db_app
from .views import main_blueprint


def create_app(config_object=DefaultConfig):
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )
    app.config.from_object(config_object)

    login_manager.init_app(app)
    init_db_app(app)

    app.register_blueprint(main_blueprint)
    app.register_blueprint(admin_blueprint)
    app.register_blueprint(admin_bot_blueprint)
    return app
