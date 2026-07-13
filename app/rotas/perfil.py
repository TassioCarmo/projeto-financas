from flask import Blueprint, redirect, render_template, url_for

from app.servicos.auth import usuario_logado

perfil_bp = Blueprint("perfil", __name__)


@perfil_bp.route("/perfil", methods=["GET"])
def exibir():
    usuario = usuario_logado()
    if not usuario:
        return redirect(url_for("auth.login"))
    return render_template("perfil.html", usuario=usuario)
