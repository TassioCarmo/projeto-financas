from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from app.servicos.auth import usuario_logado
from app.servicos.importacao import importar_transacoes
from app.servicos.transacoes import (
    CategoriaInvalidaError,
    TransacaoNaoEncontradaError,
    atualizar_transacao,
    criar_transacao,
    excluir_transacao,
    listar_por_usuario,
)

transacoes_bp = Blueprint("transacoes", __name__)


def _wants_json() -> bool:
    return (
        request.accept_mimetypes.best_match(["application/json", "text/html"])
        == "application/json"
        and request.accept_mimetypes["application/json"]
        > request.accept_mimetypes["text/html"]
    )


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "on", "yes")


def _extrair_dados_form() -> dict:
    return {
        "data_compra": request.form.get("data_compra", "").strip(),
        "descricao": request.form.get("descricao", "").strip(),
        "categoria_id": request.form.get("categoria_id", "").strip(),
        "valor": request.form.get("valor", "").strip(),
        "pago": _parse_bool(request.form.get("pago")),
        "pago_por_terceiro": _parse_bool(request.form.get("pago_por_terceiro")),
        "nome_terceiro": request.form.get("nome_terceiro", "").strip() or None,
    }


def _validar_transacao(dados: dict) -> tuple[dict | None, str | None]:
    if not dados["data_compra"]:
        return None, "Data é obrigatória."
    try:
        data_compra = datetime.strptime(dados["data_compra"], "%Y-%m-%d").date()
    except ValueError:
        return None, "Data inválida."

    if not dados["descricao"]:
        return None, "Descrição é obrigatória."

    if not dados["categoria_id"]:
        return None, "Categoria é obrigatória."
    try:
        categoria_id = int(dados["categoria_id"])
    except ValueError:
        return None, "Categoria inválida."

    if not dados["valor"]:
        return None, "Valor é obrigatório."
    try:
        valor = Decimal(dados["valor"].replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None, "Valor inválido."
    if valor <= 0:
        return None, "Valor deve ser maior que zero."

    pago = dados["pago"]
    pago_por_terceiro = dados["pago_por_terceiro"]
    nome_terceiro = dados["nome_terceiro"]

    if pago_por_terceiro and not nome_terceiro:
        return None, "Nome do terceiro é obrigatório quando pago por terceiro."

    if not pago_por_terceiro:
        nome_terceiro = None

    return {
        "data_compra": data_compra,
        "descricao": dados["descricao"],
        "categoria_id": categoria_id,
        "valor": valor,
        "pago": pago,
        "pago_por_terceiro": pago_por_terceiro,
        "nome_terceiro": nome_terceiro,
    }, None


def _requer_login():
    usuario = usuario_logado()
    if usuario:
        return usuario, None
    if _wants_json():
        return None, (jsonify({"erro": "Não autenticado."}), 401)
    return None, redirect(url_for("auth.login"))


@transacoes_bp.route("/transacoes", methods=["GET"])
def listar():
    usuario, erro = _requer_login()
    if erro:
        return erro
    transacoes = listar_por_usuario(usuario["id"])
    # Recupera resultado da última importação (se houver) e remove da session
    # para não reaparecer ao recarregar a página depois
    resultado_importacao = session.pop("ultima_importacao", None)
    return render_template(
        "transacoes/listar.html",
        transacoes=transacoes,
        resultado_importacao=resultado_importacao,
    )


@transacoes_bp.route("/transacoes", methods=["POST"])
def criar():
    usuario, erro = _requer_login()
    if erro:
        return erro

    dados = _extrair_dados_form()
    validado, msg_erro = _validar_transacao(dados)
    if msg_erro:
        flash(msg_erro, "erro")
        return render_template(
            "transacoes/listar.html",
            transacoes=listar_por_usuario(usuario["id"]),
            form=dados,
        )

    try:
        criar_transacao(usuario["id"], **validado)
    except CategoriaInvalidaError:
        flash("Categoria inválida.", "erro")
        return render_template(
            "transacoes/listar.html",
            transacoes=listar_por_usuario(usuario["id"]),
            form=dados,
        )

    flash("Transação cadastrada com sucesso.", "sucesso")
    return redirect(url_for("transacoes.listar"))


@transacoes_bp.route("/transacoes/importar", methods=["POST"])
def importar():
    # 1. Verificar login
    usuario, erro = _requer_login()
    if erro:
        return erro

    # 2. Validar arquivo enviado
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        flash("Selecione um arquivo para importar.", "erro")
        return redirect(url_for("transacoes.listar"))

    nome = arquivo.filename.lower()
    if not (nome.endswith(".csv") or nome.endswith(".xlsx")):
        flash("Formato não suportado. Use .csv ou .xlsx.", "erro")
        return redirect(url_for("transacoes.listar"))

    # 3. Chamar serviço de importação
    resultado = importar_transacoes(usuario["id"], arquivo.stream, arquivo.filename)

    # 4. Guardar resultado na session (para mostrar detalhes após redirect)
    session["ultima_importacao"] = resultado

    # 5. Flash com resumo e redirect (padrão PRG — evita reenvio ao recarregar)
    importadas = resultado["importadas"]
    qtd_erros = len(resultado["erros"])
    if importadas == 0 and qtd_erros > 0:
        flash(f"Nenhuma transação importada. {qtd_erros} linha(s) com erro.", "erro")
    elif qtd_erros > 0:
        flash(
            f"{importadas} transação(ões) importada(s). {qtd_erros} linha(s) com erro.",
            "sucesso",
        )
    else:
        flash(f"{importadas} transação(ões) importada(s) com sucesso.", "sucesso")

    return redirect(url_for("transacoes.listar"))


@transacoes_bp.route("/transacoes/<int:transacao_id>", methods=["PUT"])
def atualizar(transacao_id: int):
    usuario, erro = _requer_login()
    if erro:
        return erro

    dados = _extrair_dados_form()
    validado, msg_erro = _validar_transacao(dados)
    if msg_erro:
        if _wants_json():
            return jsonify({"erro": msg_erro}), 400
        flash(msg_erro, "erro")
        return redirect(url_for("transacoes.listar"))

    try:
        atualizar_transacao(usuario["id"], transacao_id, **validado)
    except TransacaoNaoEncontradaError:
        if _wants_json():
            return jsonify({"erro": "Transação não encontrada."}), 404
        flash("Transação não encontrada.", "erro")
        return redirect(url_for("transacoes.listar"))
    except CategoriaInvalidaError:
        if _wants_json():
            return jsonify({"erro": "Categoria inválida."}), 400
        flash("Categoria inválida.", "erro")
        return redirect(url_for("transacoes.listar"))

    if _wants_json():
        return jsonify({"sucesso": True})
    flash("Transação atualizada com sucesso.", "sucesso")
    return redirect(url_for("transacoes.listar"))


@transacoes_bp.route("/transacoes/<int:transacao_id>", methods=["DELETE"])
def excluir(transacao_id: int):
    usuario, erro = _requer_login()
    if erro:
        return erro

    try:
        excluir_transacao(usuario["id"], transacao_id)
    except TransacaoNaoEncontradaError:
        if _wants_json():
            return jsonify({"erro": "Transação não encontrada."}), 404
        flash("Transação não encontrada.", "erro")
        return redirect(url_for("transacoes.listar"))

    if _wants_json():
        return "", 204
    flash("Transação excluída com sucesso.", "sucesso")
    return redirect(url_for("transacoes.listar"))
