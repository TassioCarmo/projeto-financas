from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from app.servicos.auth import usuario_logado
from app.servicos.categorias import categoria_ativa_existe
from app.servicos.importacao import importar_transacoes
from app.servicos.perfis_importacao import listar_perfis
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


def _extrair_filtros_query() -> dict:
    """Lê os parâmetros de filtro da URL (?data_inicio=...&categoria_id=...)."""
    return {
        "data_inicio": request.args.get("data_inicio", "").strip(),
        "data_fim": request.args.get("data_fim", "").strip(),
        "categoria_id": request.args.get("categoria_id", "").strip(),
        "pago": request.args.get("pago", "").strip(),
    }


def _filtros_ativos(filtros_raw: dict) -> bool:
    """Verifica se o usuário aplicou algum filtro na listagem."""
    return any(filtros_raw.get(k) for k in ("data_inicio", "data_fim", "categoria_id", "pago"))


def _validar_filtros(dados: dict) -> tuple[dict, str | None]:
    """
    Valida filtros da query string antes de consultar o banco.

    Retorna (filtros_validados, None) ou ({}, mensagem_erro).
    Campos vazios são ignorados (não entram no filtro).
    """
    filtros: dict = {}

    # Intervalo de datas
    data_inicio = None
    data_fim = None

    if dados["data_inicio"]:
        try:
            data_inicio = datetime.strptime(dados["data_inicio"], "%Y-%m-%d").date()
        except ValueError:
            return {}, "Data início inválida."

    if dados["data_fim"]:
        try:
            data_fim = datetime.strptime(dados["data_fim"], "%Y-%m-%d").date()
        except ValueError:
            return {}, "Data fim inválida."

    if data_inicio and data_fim and data_inicio > data_fim:
        return {}, "Data início não pode ser maior que data fim."

    if data_inicio:
        filtros["data_inicio"] = data_inicio
    if data_fim:
        filtros["data_fim"] = data_fim

    # Categoria (opcional)
    if dados["categoria_id"]:
        try:
            categoria_id = int(dados["categoria_id"])
        except ValueError:
            return {}, "Categoria inválida."
        if not categoria_ativa_existe(categoria_id):
            return {}, "Categoria inválida."
        filtros["categoria_id"] = categoria_id

    # Pago: true / false / vazio (todos)
    if dados["pago"]:
        if dados["pago"].lower() not in ("true", "false"):
            return {}, "Filtro pago inválido. Use true ou false."
        filtros["pago"] = dados["pago"].lower() == "true"

    return filtros, None


def _serializar_transacao(t: dict) -> dict:
    """Converte tipos do banco para JSON serializável."""
    return {
        **t,
        "data_compra": t["data_compra"].isoformat() if t["data_compra"] else None,
        "valor": float(t["valor"]),
        "criado_em": t["criado_em"].isoformat() if t["criado_em"] else None,
        "atualizado_em": t["atualizado_em"].isoformat() if t["atualizado_em"] else None,
    }


@transacoes_bp.route("/transacoes", methods=["GET"])
def listar():
    usuario, erro = _requer_login()
    if erro:
        return erro

    filtros_raw = _extrair_filtros_query()
    filtros, msg_erro = _validar_filtros(filtros_raw)
    if msg_erro:
        if _wants_json():
            return jsonify({"erro": msg_erro}), 400
        flash(msg_erro, "erro")
        filtros = {}

    transacoes = listar_por_usuario(usuario["id"], **filtros)

    if _wants_json():
        return jsonify([_serializar_transacao(t) for t in transacoes])

    # Recupera resultado da última importação (se houver) e remove da session
    # para não reaparecer ao recarregar a página depois
    resultado_importacao = session.pop("ultima_importacao", None)
    return render_template(
        "transacoes/listar.html",
        transacoes=transacoes,
        resultado_importacao=resultado_importacao,
        filtros=filtros_raw,
        filtros_ativos=_filtros_ativos(filtros_raw),
        perfis_importacao=listar_perfis(),
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
            perfis_importacao=listar_perfis(),
        )

    try:
        criar_transacao(usuario["id"], **validado)
    except CategoriaInvalidaError:
        flash("Categoria inválida.", "erro")
        return render_template(
            "transacoes/listar.html",
            transacoes=listar_por_usuario(usuario["id"]),
            form=dados,
            perfis_importacao=listar_perfis(),
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

    perfil_id = request.form.get("perfil", "auto").strip() or "auto"

    # 3. Chamar serviço de importação
    resultado = importar_transacoes(
        usuario["id"], arquivo.stream, arquivo.filename, perfil_id=perfil_id
    )

    # 4. Guardar resultado na session (para mostrar detalhes após redirect)
    session["ultima_importacao"] = resultado

    # 5. Flash com resumo e redirect (padrão PRG — evita reenvio ao recarregar)
    importadas = resultado["importadas"]
    qtd_erros = len(resultado["erros"])
    erro_perfil = (
        qtd_erros == 1
        and resultado["erros"][0]["linha"] == 0
        and "perfil" in resultado["erros"][0]["mensagem"].lower()
    )
    if importadas == 0 and qtd_erros > 0:
        if erro_perfil:
            flash(resultado["erros"][0]["mensagem"], "erro")
        else:
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
