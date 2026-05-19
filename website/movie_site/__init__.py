from flask import Flask

from .admin_bot import admin_bot_blueprint, oauth_callback
from .auth import login_manager
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

    login_manager.init_app(app)
    init_db_app(app)

    app.register_blueprint(main_blueprint)
    app.register_blueprint(admin_bot_blueprint)
    app.add_url_rule(
        '/oauth/discord/callback',
        endpoint='discord_oauth_callback',
        view_func=oauth_callback,
        methods=['GET'],
    )
    return app
