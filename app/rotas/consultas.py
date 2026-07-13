import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app.servicos.auth import usuario_logado
from app.servicos.categorias import categoria_ativa_existe
from app.servicos.consultas import (
    CAMPOS_PERMITIDOS,
    MAX_CONDICOES,
    OPERADORES_POR_CAMPO,
    POR_PAGINA_MAX,
    POR_PAGINA_PADRAO,
    consultar_transacoes,
)

consultas_bp = Blueprint("consultas", __name__)

_INDICE_RE = re.compile(r"^f(\d+)_(campo|operador|valor|valor2)$")


def _mes_atual() -> str:
    agora = datetime.now()
    return f"{agora.year}-{agora.month:02d}"


def _contexto_html(**kwargs):
    return {
        "ano_mes": _mes_atual(),
        "pagina_ativa": "consultas",
        **kwargs,
    }


def _wants_json() -> bool:
    return (
        request.accept_mimetypes.best_match(["application/json", "text/html"])
        == "application/json"
        and request.accept_mimetypes["application/json"]
        > request.accept_mimetypes["text/html"]
    )


def _requer_login():
    usuario = usuario_logado()
    if usuario:
        return usuario, None
    if _wants_json():
        return None, (jsonify({"erro": "Não autenticado."}), 401)
    return None, redirect(url_for("auth.login"))


def _serializar_transacao(t: dict) -> dict:
    return {
        **t,
        "data_compra": t["data_compra"].isoformat() if t["data_compra"] else None,
        "valor": float(t["valor"]),
        "criado_em": t["criado_em"].isoformat() if t["criado_em"] else None,
        "atualizado_em": t["atualizado_em"].isoformat() if t["atualizado_em"] else None,
    }


def _serializar_condicao(condicao: dict) -> dict:
    serializada = {
        "campo": condicao["campo"],
        "operador": condicao["operador"],
        "valor": condicao["valor_raw"],
    }
    if "valor2_raw" in condicao:
        serializada["valor2"] = condicao["valor2_raw"]
    return serializada


def _extrair_condicoes_raw() -> list[dict]:
    """Agrupa parâmetros f{N}_* da query string em blocos de condição."""
    blocos: dict[int, dict] = {}

    for chave, valor in request.args.items():
        match = _INDICE_RE.match(chave)
        if not match:
            continue
        indice = int(match.group(1))
        campo_chave = match.group(2)
        blocos.setdefault(indice, {})[campo_chave] = valor.strip()

    return [blocos[i] for i in sorted(blocos)]


def _validar_condicao(bruto: dict) -> tuple[dict | None, str | None]:
    campo = bruto.get("campo", "").strip()
    operador = bruto.get("operador", "").strip()
    valor_raw = bruto.get("valor", "").strip()
    valor2_raw = bruto.get("valor2", "").strip()

    if not campo:
        return None, "Campo do filtro é obrigatório."
    if campo not in CAMPOS_PERMITIDOS:
        return None, f"Campo inválido: {campo}."
    if not operador:
        return None, "Operador do filtro é obrigatório."
    if operador not in OPERADORES_POR_CAMPO[campo]:
        return None, f"Operador inválido para o campo {campo}."

    condicao: dict = {
        "campo": campo,
        "operador": operador,
        "valor_raw": valor_raw,
    }

    if campo == "categoria":
        if operador == "igual":
            if not valor_raw:
                return None, "Valor da categoria é obrigatório."
            try:
                categoria_id = int(valor_raw)
            except ValueError:
                return None, "Categoria inválida."
            if not categoria_ativa_existe(categoria_id):
                return None, "Categoria inválida."
            condicao["valor"] = categoria_id
        elif operador == "contem":
            if not valor_raw:
                return None, "Texto da categoria é obrigatório."
            condicao["valor"] = valor_raw

    elif campo == "data_compra":
        if operador == "entre":
            if not valor_raw or not valor2_raw:
                return None, "Intervalo de datas incompleto."
            try:
                data_inicio = datetime.strptime(valor_raw, "%Y-%m-%d").date()
                data_fim = datetime.strptime(valor2_raw, "%Y-%m-%d").date()
            except ValueError:
                return None, "Data inválida."
            if data_inicio > data_fim:
                return None, "Data início não pode ser maior que data fim."
            condicao["valor"] = data_inicio
            condicao["valor2"] = data_fim
            condicao["valor2_raw"] = valor2_raw
        else:
            if not valor_raw:
                return None, "Data é obrigatória."
            try:
                condicao["valor"] = datetime.strptime(valor_raw, "%Y-%m-%d").date()
            except ValueError:
                return None, "Data inválida."

    elif campo == "valor":
        if operador == "entre":
            if not valor_raw or not valor2_raw:
                return None, "Intervalo de valores incompleto."
            try:
                valor_inicio = Decimal(valor_raw.replace(",", "."))
                valor_fim = Decimal(valor2_raw.replace(",", "."))
            except (InvalidOperation, AttributeError):
                return None, "Valor inválido."
            if valor_inicio > valor_fim:
                return None, "Valor mínimo não pode ser maior que valor máximo."
            condicao["valor"] = valor_inicio
            condicao["valor2"] = valor_fim
            condicao["valor2_raw"] = valor2_raw
        else:
            if not valor_raw:
                return None, "Valor é obrigatório."
            try:
                condicao["valor"] = Decimal(valor_raw.replace(",", "."))
            except (InvalidOperation, AttributeError):
                return None, "Valor inválido."

    elif campo in ("pago", "pago_por_terceiro"):
        if not valor_raw:
            return None, "Valor é obrigatório."
        if valor_raw.lower() not in ("true", "false"):
            return None, "Valor booleano inválido. Use true ou false."
        condicao["valor"] = valor_raw.lower() == "true"

    return condicao, None


def _validar_condicoes(brutos: list[dict]) -> tuple[list[dict], str | None]:
    if len(brutos) > MAX_CONDICOES:
        return [], f"Máximo de {MAX_CONDICOES} condições permitidas."

    validadas: list[dict] = []
    for bruto in brutos:
        condicao, erro = _validar_condicao(bruto)
        if erro:
            return [], erro
        validadas.append(condicao)

    return validadas, None


def _validar_paginacao() -> tuple[int, int, str | None]:
    pagina_raw = request.args.get("pagina", "1").strip()
    por_pagina_raw = request.args.get("por_pagina", str(POR_PAGINA_PADRAO)).strip()

    try:
        pagina = int(pagina_raw)
    except ValueError:
        return 1, POR_PAGINA_PADRAO, "Página inválida."

    try:
        por_pagina = int(por_pagina_raw)
    except ValueError:
        return 1, POR_PAGINA_PADRAO, "Itens por página inválidos."

    if pagina < 1:
        return 1, POR_PAGINA_PADRAO, "Página deve ser maior ou igual a 1."
    if por_pagina < 1 or por_pagina > POR_PAGINA_MAX:
        return 1, POR_PAGINA_PADRAO, f"Itens por página deve estar entre 1 e {POR_PAGINA_MAX}."

    return pagina, por_pagina, None


@consultas_bp.route("/consultas", methods=["GET"])
def listar():
    usuario, erro = _requer_login()
    if erro:
        return erro

    condicoes_raw = _extrair_condicoes_raw()
    condicoes, msg_erro = _validar_condicoes(condicoes_raw)
    pagina, por_pagina, msg_paginacao = _validar_paginacao()

    if msg_erro or msg_paginacao:
        mensagem = msg_erro or msg_paginacao
        if _wants_json():
            return jsonify({"erro": mensagem}), 400
        flash(mensagem, "erro")
        return render_template(
            "consultas/listar.html",
            **_contexto_html(
                transacoes=[],
                condicoes=condicoes_raw,
                paginacao={
                    "pagina": pagina,
                    "por_pagina": por_pagina,
                    "total": 0,
                    "total_paginas": 0,
                },
                max_condicoes=MAX_CONDICOES,
            ),
        )

    resultado = consultar_transacoes(
        usuario["id"],
        condicoes=condicoes,
        pagina=pagina,
        por_pagina=por_pagina,
    )

    if _wants_json():
        return jsonify(
            {
                "transacoes": [
                    _serializar_transacao(t) for t in resultado["transacoes"]
                ],
                "paginacao": {
                    "pagina": resultado["pagina"],
                    "por_pagina": resultado["por_pagina"],
                    "total": resultado["total"],
                    "total_paginas": resultado["total_paginas"],
                },
                "condicoes_aplicadas": [
                    _serializar_condicao(c) for c in condicoes
                ],
            }
        )

    return render_template(
        "consultas/listar.html",
        **_contexto_html(
            transacoes=resultado["transacoes"],
            condicoes=condicoes_raw,
            paginacao={
                "pagina": resultado["pagina"],
                "por_pagina": resultado["por_pagina"],
                "total": resultado["total"],
                "total_paginas": resultado["total_paginas"],
            },
            max_condicoes=MAX_CONDICOES,
        ),
    )
