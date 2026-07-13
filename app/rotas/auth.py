from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.servicos.auth import encerrar_sessao, iniciar_sessao
from app.servicos.usuarios import (
    EmailJaCadastradoError,
    buscar_por_email,
    criar_usuario,
    verificar_senha,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _validar_cadastro(nome: str, email: str, senha: str) -> str | None:
    if not nome.strip():
        return "Nome é obrigatório."
    if not email.strip():
        return "Email é obrigatório."
    if "@" not in email:
        return "Email inválido."
    if len(senha) < 6:
        return "Senha deve ter pelo menos 6 caracteres."
    return None


def _validar_login(email: str, senha: str) -> str | None:
    if not email.strip():
        return "Email é obrigatório."
    if not senha:
        return "Senha é obrigatória."
    return None


@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "GET":
        return render_template("auth/cadastro.html")

    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")

    erro = _validar_cadastro(nome, email, senha)
    if erro:
        flash(erro, "erro")
        return render_template("auth/cadastro.html", nome=nome, email=email)

    try:
        criar_usuario(nome, email, senha)
    except EmailJaCadastradoError:
        flash("Email já cadastrado.", "erro")
        return render_template("auth/cadastro.html", nome=nome, email=email)

    flash("Cadastro realizado com sucesso. Faça login.", "sucesso")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")

    erro = _validar_login(email, senha)
    if erro:
        flash(erro, "erro")
        return render_template("auth/login.html", email=email)

    usuario = buscar_por_email(email)
    if not usuario or not verificar_senha(senha, usuario["senha_hash"]):
        flash("Email ou senha incorretos.", "erro")
        return render_template("auth/login.html", email=email)

    iniciar_sessao(usuario)
    return redirect(url_for("perfil.exibir"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    encerrar_sessao()
    flash("Logout realizado com sucesso.", "sucesso")
    return redirect(url_for("auth.login"))
