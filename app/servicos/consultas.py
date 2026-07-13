from datetime import date
from decimal import Decimal
from math import ceil

from app.servicos.db import get_connection
from app.servicos.transacoes import _row_to_dict

CAMPOS_PERMITIDOS = {"categoria", "data_compra", "valor", "pago", "pago_por_terceiro"}
OPERADORES_POR_CAMPO = {
    "categoria": {"igual", "contem"},
    "data_compra": {"igual", "maior_que", "menor_que", "entre"},
    "valor": {"igual", "maior_que", "menor_que", "entre"},
    "pago": {"igual"},
    "pago_por_terceiro": {"igual"},
}
MAX_CONDICOES = 5
POR_PAGINA_PADRAO = 25
POR_PAGINA_MAX = 100

_BASE_FROM = """
    FROM transacoes t
    JOIN categorias c ON c.id = t.categoria_id
"""


def _condicao_para_sql(condicao: dict) -> tuple[str, list]:
    """Converte uma condição validada em fragmento SQL + parâmetros."""
    campo = condicao["campo"]
    operador = condicao["operador"]

    if campo == "categoria" and operador == "igual":
        return "t.categoria_id = %s", [condicao["valor"]]
    if campo == "categoria" and operador == "contem":
        return "c.nome ILIKE %s", [f"%{condicao['valor']}%"]

    if campo == "data_compra":
        if operador == "igual":
            return "t.data_compra = %s", [condicao["valor"]]
        if operador == "maior_que":
            return "t.data_compra > %s", [condicao["valor"]]
        if operador == "menor_que":
            return "t.data_compra < %s", [condicao["valor"]]
        if operador == "entre":
            return "t.data_compra BETWEEN %s AND %s", [
                condicao["valor"],
                condicao["valor2"],
            ]

    if campo == "valor":
        if operador == "igual":
            return "t.valor = %s", [condicao["valor"]]
        if operador == "maior_que":
            return "t.valor > %s", [condicao["valor"]]
        if operador == "menor_que":
            return "t.valor < %s", [condicao["valor"]]
        if operador == "entre":
            return "t.valor BETWEEN %s AND %s", [
                condicao["valor"],
                condicao["valor2"],
            ]

    if campo == "pago" and operador == "igual":
        return "t.pago = %s", [condicao["valor"]]
    if campo == "pago_por_terceiro" and operador == "igual":
        return "t.pago_por_terceiro = %s", [condicao["valor"]]

    raise ValueError("Condição inválida.")


def _montar_where(usuario_id: str, condicoes: list[dict]) -> tuple[str, list]:
    where = ["t.usuario_id = %s"]
    params: list = [usuario_id]

    for condicao in condicoes:
        fragmento, fragmento_params = _condicao_para_sql(condicao)
        where.append(fragmento)
        params.extend(fragmento_params)

    return " AND ".join(where), params


def consultar_transacoes(
    usuario_id: str,
    condicoes: list[dict] | None = None,
    pagina: int = 1,
    por_pagina: int = POR_PAGINA_PADRAO,
) -> dict:
    """
    Consulta transações com filtros dinâmicos e paginação.

    Condições devem vir já validadas pela camada de rota.
    """
    condicoes = condicoes or []
    where_sql, params = _montar_where(usuario_id, condicoes)
    offset = (pagina - 1) * por_pagina

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) {_BASE_FROM} WHERE {where_sql}",
                params,
            )
            total = cur.fetchone()[0]

            cur.execute(
                f"""
                SELECT
                    t.id, t.data_compra, t.descricao, t.categoria_id, c.nome,
                    t.valor, t.pago, t.pago_por_terceiro, t.nome_terceiro,
                    t.origem, t.criado_em, t.atualizado_em
                {_BASE_FROM}
                WHERE {where_sql}
                ORDER BY t.data_compra DESC, t.id DESC
                LIMIT %s OFFSET %s
                """,
                [*params, por_pagina, offset],
            )
            transacoes = [_row_to_dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    total_paginas = ceil(total / por_pagina) if total > 0 else 0

    return {
        "transacoes": transacoes,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
    }
