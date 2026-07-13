"""
Rotas de orçamentos — GET (tela + status), POST (criar/atualizar).

GET  /orcamentos?ano_mes=2026-07           → tela HTML com form + tabela de status
POST /orcamentos                           → salva/atualiza orçamento (upsert)
GET  /orcamentos/<ano_mes>/status          → JSON com planejado vs. gasto real
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app.servicos.auth import usuario_logado
from app.servicos.orcamentos import salvar_orcamento, status_por_mes

orcamentos_bp = Blueprint("orcamentos", __name__)


def _wants_json() -> bool:
    """Verifica se o cliente prefere resposta JSON em vez de HTML."""
    return (
        request.accept_mimetypes.best_match(["application/json", "text/html"])
        == "application/json"
        and request.accept_mimetypes["application/json"]
        > request.accept_mimetypes["text/html"]
    )


def _requer_login():
    """Garante que o usuário está logado. Retorna (usuario, None) ou (None, resposta_erro)."""
    usuario = usuario_logado()
    if usuario:
        return usuario, None
    if _wants_json():
        return None, (jsonify({"erro": "Não autenticado."}), 401)
    return None, redirect(url_for("auth.login"))


def _mes_atual() -> str:
    """Retorna o mês atual no formato AAAA-MM."""
    agora = datetime.now()
    return f"{agora.year}-{agora.month:02d}"


def _parse_ano_mes(valor: str | None) -> tuple[str | None, str | None]:
    """
    Valida o parâmetro ano_mes.

    Retorna (ano_mes, None) se válido ou (None, mensagem_erro).
    Se valor for vazio, usa o mês atual.
    """
    if not valor or not valor.strip():
        return _mes_atual(), None

    ano_mes = valor.strip()
    if not re.match(r"^\d{4}-\d{2}$", ano_mes):
        return None, "Mês inválido. Use o formato AAAA-MM."

    mes = int(ano_mes.split("-")[1])
    if mes < 1 or mes > 12:
        return None, "Mês inválido. Use um valor entre 01 e 12."

    return ano_mes, None


def _parse_decimal(valor: str, nome_campo: str) -> tuple[Decimal | None, str | None]:
    """Converte string do formulário em Decimal. Aceita vírgula ou ponto."""
    valor = valor.strip() if valor else ""

    if not valor:
        return None, f"{nome_campo} é obrigatório."

    try:
        return Decimal(valor.replace(",", ".")), None
    except (InvalidOperation, AttributeError):
        return None, f"{nome_campo} inválido."


def _extrair_dados_form() -> dict:
    """Lê os campos enviados pelo formulário HTML."""
    return {
        "ano_mes": request.form.get("ano_mes", "").strip(),
        "categoria_id": request.form.get("categoria_id", "").strip(),
        "valor_planejado": request.form.get("valor_planejado", "").strip(),
    }


def _validar_orcamento(dados: dict) -> tuple[dict | None, str | None]:
    """
    Valida os dados do formulário antes de salvar.

    Retorna (dados_validados, None) ou (None, mensagem_erro).
    """
    if not dados["ano_mes"]:
        return None, "Mês é obrigatório."

    _, msg_erro = _parse_ano_mes(dados["ano_mes"])
    if msg_erro:
        return None, msg_erro

    if not dados["categoria_id"]:
        return None, "Categoria é obrigatória."

    try:
        categoria_id = int(dados["categoria_id"])
    except ValueError:
        return None, "Categoria inválida."

    valor_planejado, erro = _parse_decimal(dados["valor_planejado"], "Valor planejado")
    if erro:
        return None, erro

    if valor_planejado < 0:
        return None, "Valor planejado não pode ser negativo."

    return {
        "ano_mes": dados["ano_mes"],
        "categoria_id": categoria_id,
        "valor_planejado": valor_planejado,
    }, None


def _serializar_status(item: dict) -> dict:
    """Converte Decimals para float para resposta JSON."""
    return {
        **item,
        "valor_planejado": float(item["valor_planejado"]),
        "valor_gasto": float(item["valor_gasto"]),
        "saldo_restante": float(item["saldo_restante"]),
        "percentual_usado": (
            float(item["percentual_usado"])
            if item["percentual_usado"] is not None
            else None
        ),
    }


def _render_lista(usuario_id: str, ano_mes: str, form: dict | None = None):
    """Monta a resposta HTML da tela de orçamentos."""
    status = status_por_mes(usuario_id, ano_mes)
    return render_template(
        "orcamentos/listar.html",
        status=status,
        ano_mes=ano_mes,
        form=form,
    )


@orcamentos_bp.route("/orcamentos", methods=["GET"])
def listar():
    """
    Tela de orçamentos: filtro de mês, formulário e tabela de status.

    Query param: ?ano_mes=2026-07 (padrão: mês atual)
    """
    usuario, erro = _requer_login()
    if erro:
        return erro

    ano_mes, msg_erro = _parse_ano_mes(request.args.get("ano_mes"))
    if msg_erro:
        flash(msg_erro, "erro")
        ano_mes = _mes_atual()

    return _render_lista(usuario["id"], ano_mes)


@orcamentos_bp.route("/orcamentos", methods=["POST"])
def salvar():
    """
    Cria ou atualiza um orçamento (upsert por usuario_id + categoria_id + ano_mes).

    Após salvar, redireciona para GET com o mesmo ano_mes.
    """
    usuario, erro = _requer_login()
    if erro:
        return erro

    dados = _extrair_dados_form()
    validado, msg_erro = _validar_orcamento(dados)

    ano_mes_redirect = dados.get("ano_mes") or _mes_atual()

    if msg_erro:
        flash(msg_erro, "erro")
        return _render_lista(usuario["id"], ano_mes_redirect, form=dados)

    salvar_orcamento(usuario["id"], **validado)

    flash(
        f"Orçamento de {validado['ano_mes']} salvo com sucesso.",
        "sucesso",
    )
    return redirect(url_for("orcamentos.listar", ano_mes=validado["ano_mes"]))


@orcamentos_bp.route("/orcamentos/<ano_mes>/status", methods=["GET"])
def status(ano_mes: str):
    """
    Compara planejado vs. gasto real por categoria no mês.

    JSON: array de status (se Accept: application/json)
    HTML: redirect para tela principal com o mês selecionado
    """
    usuario, erro = _requer_login()
    if erro:
        return erro

    _, msg_erro = _parse_ano_mes(ano_mes)
    if msg_erro:
        if _wants_json():
            return jsonify({"erro": msg_erro}), 400
        flash(msg_erro, "erro")
        return redirect(url_for("orcamentos.listar"))

    status_list = status_por_mes(usuario["id"], ano_mes)

    if _wants_json():
        return jsonify([_serializar_status(s) for s in status_list])

    return redirect(url_for("orcamentos.listar", ano_mes=ano_mes))
