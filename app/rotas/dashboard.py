"""
Rotas de agregação para o dashboard (JSON).

GET /dashboard/fluxo-caixa?ano_mes=
GET /dashboard/compras-recorrentes?ano_mes=
GET /dashboard/categorias-top?ano_mes=
GET /dashboard/patrimonio
GET /dashboard/orcamentos-resumo?ano_mes=
"""

import re
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request

from app.servicos.auth import usuario_logado
from app.servicos.dashboard import (
    categorias_top,
    compras_recorrentes,
    fluxo_caixa,
    orcamentos_resumo,
    patrimonio_evolucao,
)

dashboard_bp = Blueprint("dashboard", __name__)


def _requer_login():
    usuario = usuario_logado()
    if usuario:
        return usuario, None
    return None, (jsonify({"erro": "Não autenticado."}), 401)


def _mes_atual() -> str:
    agora = datetime.now()
    return f"{agora.year}-{agora.month:02d}"


def _parse_ano_mes(valor: str | None) -> tuple[str | None, str | None]:
    if not valor or not valor.strip():
        return _mes_atual(), None

    ano_mes = valor.strip()
    if not re.match(r"^\d{4}-\d{2}$", ano_mes):
        return None, "Mês inválido. Use o formato AAAA-MM."

    mes = int(ano_mes.split("-")[1])
    if mes < 1 or mes > 12:
        return None, "Mês inválido. Use um valor entre 01 e 12."

    return ano_mes, None


def _float_or_none(valor) -> float | None:
    if valor is None:
        return None
    return float(valor)


def _serializar_fluxo_bloco(bloco: dict) -> dict:
    return {
        "entrou": float(bloco["entrou"]),
        "saiu": float(bloco["saiu"]),
        "saldo": float(bloco["saldo"]),
    }


def _serializar_compra(item: dict) -> dict:
    return {
        **item,
        "total": float(item["total"]),
        "media": float(item["media"]),
    }


def _serializar_categoria(item: dict) -> dict:
    return {
        **item,
        "total": float(item["total"]),
        "percentual": _float_or_none(item["percentual"]),
    }


def _serializar_patrimonio(item: dict) -> dict:
    return {
        "ano_mes": item["ano_mes"],
        "renda": float(item["renda"]) if item["renda"] is not None else 0.0,
        "investimento": (
            float(item["investimento"]) if item["investimento"] is not None else 0.0
        ),
        "rendimentos": (
            float(item["rendimentos"]) if item["rendimentos"] is not None else 0.0
        ),
        "patrimonio": _float_or_none(item["patrimonio"]),
        "patrimonio_sugerido": _float_or_none(item["patrimonio_sugerido"]),
        "patrimonio_efetivo": _float_or_none(item["patrimonio_efetivo"]),
    }


def _serializar_status(item: dict) -> dict:
    return {
        **item,
        "valor_planejado": float(item["valor_planejado"]),
        "valor_gasto": float(item["valor_gasto"]),
        "saldo_restante": float(item["saldo_restante"]),
        "percentual_usado": _float_or_none(item["percentual_usado"]),
    }


def _parse_ano_mes_request() -> tuple[str | None, tuple | None]:
    ano_mes, msg_erro = _parse_ano_mes(request.args.get("ano_mes"))
    if msg_erro:
        return None, (jsonify({"erro": msg_erro}), 400)
    return ano_mes, None


@dashboard_bp.route("/dashboard/fluxo-caixa", methods=["GET"])
def rota_fluxo_caixa():
    usuario, erro = _requer_login()
    if erro:
        return erro

    ano_mes, erro = _parse_ano_mes_request()
    if erro:
        return erro

    dados = fluxo_caixa(usuario["id"], ano_mes)
    return jsonify(
        {
            "ano_mes": dados["ano_mes"],
            "mes": _serializar_fluxo_bloco(dados["mes"]),
            "total_geral": _serializar_fluxo_bloco(dados["total_geral"]),
        }
    )


@dashboard_bp.route("/dashboard/compras-recorrentes", methods=["GET"])
def rota_compras_recorrentes():
    usuario, erro = _requer_login()
    if erro:
        return erro

    ano_mes, erro = _parse_ano_mes_request()
    if erro:
        return erro

    dados = compras_recorrentes(usuario["id"], ano_mes)
    return jsonify(
        {
            "ano_mes": dados["ano_mes"],
            "mes": [_serializar_compra(item) for item in dados["mes"]],
            "total_geral": [
                _serializar_compra(item) for item in dados["total_geral"]
            ],
        }
    )


@dashboard_bp.route("/dashboard/categorias-top", methods=["GET"])
def rota_categorias_top():
    usuario, erro = _requer_login()
    if erro:
        return erro

    ano_mes, erro = _parse_ano_mes_request()
    if erro:
        return erro

    dados = categorias_top(usuario["id"], ano_mes)
    return jsonify(
        {
            "ano_mes": dados["ano_mes"],
            "mes": [_serializar_categoria(item) for item in dados["mes"]],
            "total_geral": [
                _serializar_categoria(item) for item in dados["total_geral"]
            ],
        }
    )


@dashboard_bp.route("/dashboard/patrimonio", methods=["GET"])
def rota_patrimonio():
    usuario, erro = _requer_login()
    if erro:
        return erro

    dados = patrimonio_evolucao(usuario["id"])
    return jsonify(
        {"serie": [_serializar_patrimonio(item) for item in dados["serie"]]}
    )


@dashboard_bp.route("/dashboard/orcamentos-resumo", methods=["GET"])
def rota_orcamentos_resumo():
    usuario, erro = _requer_login()
    if erro:
        return erro

    ano_mes, erro = _parse_ano_mes_request()
    if erro:
        return erro

    dados = orcamentos_resumo(usuario["id"], ano_mes)
    totais = dados["totais"]
    return jsonify(
        {
            "ano_mes": dados["ano_mes"],
            "totais": {
                "valor_planejado": float(totais["valor_planejado"]),
                "valor_gasto": float(totais["valor_gasto"]),
                "saldo_restante": float(totais["saldo_restante"]),
                "percentual_usado": _float_or_none(totais["percentual_usado"]),
            },
            "por_categoria": [
                _serializar_status(item) for item in dados["por_categoria"]
            ],
        }
    )
