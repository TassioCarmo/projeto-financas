"""
Rotas do resumo mensal — GET (listar por ano) e POST (criar/atualizar).

GET  /resumo-mensal?ano=2026  → tela HTML ou JSON
POST /resumo-mensal           → salva/atualiza um mês (upsert)
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app.servicos.auth import usuario_logado
from app.servicos.resumo_mensal import listar_por_ano, salvar_resumo

resumo_mensal_bp = Blueprint("resumo_mensal", __name__)


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


def _parse_ano(valor: str | None) -> tuple[int | None, str | None]:
    """
    Valida o parâmetro ?ano= da URL.

    Retorna (ano, None) se válido ou (None, mensagem_erro).
    Se valor for vazio, usa o ano atual.
    """
    if not valor or not valor.strip():
        return datetime.now().year, None

    try:
        ano = int(valor.strip())
    except ValueError:
        return None, "Ano inválido."

    if ano < 2000 or ano > 2100:
        return None, "Ano deve estar entre 2000 e 2100."

    return ano, None


def _parse_decimal(valor: str, nome_campo: str, obrigatorio: bool = True) -> tuple[Decimal | None, str | None]:
    """
    Converte string do formulário em Decimal.

    Aceita vírgula ou ponto como separador decimal.
    Se obrigatorio=False e valor vazio, retorna (None, None).
    """
    valor = valor.strip() if valor else ""

    if not valor:
        if obrigatorio:
            return None, f"{nome_campo} é obrigatório."
        return None, None

    try:
        return Decimal(valor.replace(",", ".")), None
    except (InvalidOperation, AttributeError):
        return None, f"{nome_campo} inválido."


def _extrair_dados_form() -> dict:
    """Lê os campos enviados pelo formulário HTML."""
    return {
        "ano_mes": request.form.get("ano_mes", "").strip(),
        "renda": request.form.get("renda", "").strip(),
        "investimento": request.form.get("investimento", "").strip(),
        "rendimentos": request.form.get("rendimentos", "").strip(),
        "patrimonio": request.form.get("patrimonio", "").strip(),
    }


def _validar_resumo(dados: dict) -> tuple[dict | None, str | None]:
    """
    Valida os dados do formulário antes de salvar.

    Retorna (dados_validados, None) ou (None, mensagem_erro).
    """
    # Mês no formato "2026-07" (vem do input type="month")
    if not dados["ano_mes"]:
        return None, "Mês é obrigatório."

    import re

    if not re.match(r"^\d{4}-\d{2}$", dados["ano_mes"]):
        return None, "Mês inválido. Use o formato AAAA-MM."

    renda, erro = _parse_decimal(dados["renda"], "Renda")
    if erro:
        return None, erro

    investimento, erro = _parse_decimal(dados["investimento"], "Investimento")
    if erro:
        return None, erro

    rendimentos, erro = _parse_decimal(dados["rendimentos"], "Rendimentos")
    if erro:
        return None, erro

    # Patrimônio manual é opcional
    patrimonio, erro = _parse_decimal(dados["patrimonio"], "Patrimônio", obrigatorio=False)
    if erro:
        return None, erro

    return {
        "ano_mes": dados["ano_mes"],
        "renda": renda,
        "investimento": investimento,
        "rendimentos": rendimentos,
        "patrimonio": patrimonio,
    }, None


def _render_lista(usuario_id: str, ano: int, form: dict | None = None):
    """Monta a resposta HTML da tela de resumo mensal."""
    resumos = listar_por_ano(usuario_id, ano)
    return render_template(
        "resumo_mensal/listar.html",
        resumos=resumos,
        ano=ano,
        form=form,
    )


@resumo_mensal_bp.route("/resumo-mensal", methods=["GET"])
def listar():
    """
    Lista os resumos mensais de um ano.

    Query param: ?ano=2026 (padrão: ano atual)
    HTML: tela com formulário + tabela
    JSON: array de registros (se Accept: application/json)
    """
    usuario, erro = _requer_login()
    if erro:
        return erro

    ano, msg_erro = _parse_ano(request.args.get("ano"))
    if msg_erro:
        if _wants_json():
            return jsonify({"erro": msg_erro}), 400
        flash(msg_erro, "erro")
        ano = datetime.now().year

    resumos = listar_por_ano(usuario["id"], ano)

    if _wants_json():
        # Converte Decimal para float para JSON serializar
        def _serializar(r):
            return {
                **r,
                "renda": float(r["renda"]),
                "investimento": float(r["investimento"]),
                "rendimentos": float(r["rendimentos"]),
                "patrimonio": float(r["patrimonio"]) if r["patrimonio"] is not None else None,
                "patrimonio_sugerido": (
                    float(r["patrimonio_sugerido"])
                    if r["patrimonio_sugerido"] is not None
                    else None
                ),
                "criado_em": r["criado_em"].isoformat() if r["criado_em"] else None,
                "atualizado_em": r["atualizado_em"].isoformat() if r["atualizado_em"] else None,
            }

        return jsonify([_serializar(r) for r in resumos])

    return render_template(
        "resumo_mensal/listar.html",
        resumos=resumos,
        ano=ano,
        form=None,
    )


@resumo_mensal_bp.route("/resumo-mensal", methods=["POST"])
def salvar():
    """
    Cria ou atualiza o resumo de um mês (upsert por usuario_id + ano_mes).

    Após salvar, redireciona para GET com o ano do mês salvo.
    """
    usuario, erro = _requer_login()
    if erro:
        return erro

    dados = _extrair_dados_form()
    validado, msg_erro = _validar_resumo(dados)

    # Extrai o ano do ano_mes para redirect e re-render em caso de erro
    ano_redirect = datetime.now().year
    if dados.get("ano_mes") and len(dados["ano_mes"]) >= 4:
        try:
            ano_redirect = int(dados["ano_mes"][:4])
        except ValueError:
            pass

    if msg_erro:
        flash(msg_erro, "erro")
        return _render_lista(usuario["id"], ano_redirect, form=dados)

    salvar_resumo(usuario["id"], **validado)

    flash(f"Resumo de {validado['ano_mes']} salvo com sucesso.", "sucesso")
    return redirect(url_for("resumo_mensal.listar", ano=ano_redirect))
