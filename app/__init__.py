from flask import Flask

from app.config import Config
from app.rotas.health import health_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.register_blueprint(health_bp)

    return app
