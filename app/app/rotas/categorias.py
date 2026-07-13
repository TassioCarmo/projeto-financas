from flask import Blueprint, jsonify, redirect, url_for

from app.servicos.auth import usuario_logado
from app.servicos.categorias import listar_ativas

categorias_bp = Blueprint("categorias", __name__)


@categorias_bp.route("/categorias", methods=["GET"])
def listar():
    usuario = usuario_logado()
    if not usuario:
        return jsonify({"erro": "Não autenticado."}), 401
    return jsonify(listar_ativas())
