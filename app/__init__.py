from flask import Flask

from app.config import Config
from app.rotas.auth import auth_bp
from app.rotas.categorias import categorias_bp
from app.rotas.consultas import consultas_bp
from app.rotas.dashboard import dashboard_bp
from app.rotas.health import health_bp
from app.rotas.perfil import perfil_bp
from app.rotas.orcamentos import orcamentos_bp
from app.rotas.resumo_mensal import resumo_mensal_bp
from app.rotas.transacoes import transacoes_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(perfil_bp)
    app.register_blueprint(categorias_bp)
    app.register_blueprint(consultas_bp)
    app.register_blueprint(transacoes_bp)
    app.register_blueprint(resumo_mensal_bp)
    app.register_blueprint(orcamentos_bp)
    app.register_blueprint(dashboard_bp)

    return app
