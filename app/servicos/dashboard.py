"""
Serviço de agregações para o dashboard.

Todas as consultas filtram por usuario_id da sessão.
Entrou = renda + rendimentos (resumo_mensal); saiu = soma de transacoes.valor.
"""

from decimal import Decimal

from app.servicos.db import get_connection
from app.servicos.orcamentos import _calcular_percentual, status_por_mes


def _decimal(valor) -> Decimal:
    if valor is None:
        return Decimal("0")
    return Decimal(str(valor))


def _bloco_fluxo(entrou: Decimal, saiu: Decimal) -> dict:
    return {
        "entrou": entrou,
        "saiu": saiu,
        "saldo": entrou - saiu,
    }


def _soma_gastos(conn, usuario_id: str, ano_mes: str | None = None) -> Decimal:
    with conn.cursor() as cur:
        if ano_mes:
            cur.execute(
                """
                SELECT COALESCE(SUM(valor), 0)
                FROM transacoes
                WHERE usuario_id = %s
                  AND TO_CHAR(data_compra, 'YYYY-MM') = %s
                """,
                (usuario_id, ano_mes),
            )
        else:
            cur.execute(
                """
                SELECT COALESCE(SUM(valor), 0)
                FROM transacoes
                WHERE usuario_id = %s
                """,
                (usuario_id,),
            )
        return _decimal(cur.fetchone()[0])


def _soma_entrou(conn, usuario_id: str, ano_mes: str | None = None) -> Decimal:
    with conn.cursor() as cur:
        if ano_mes:
            cur.execute(
                """
                SELECT COALESCE(renda, 0), COALESCE(rendimentos, 0)
                FROM resumo_mensal
                WHERE usuario_id = %s AND ano_mes = %s
                """,
                (usuario_id, ano_mes),
            )
            row = cur.fetchone()
            if not row:
                return Decimal("0")
            return _decimal(row[0]) + _decimal(row[1])

        cur.execute(
            """
            SELECT COALESCE(SUM(renda), 0), COALESCE(SUM(rendimentos), 0)
            FROM resumo_mensal
            WHERE usuario_id = %s
            """,
            (usuario_id,),
        )
        row = cur.fetchone()
        return _decimal(row[0]) + _decimal(row[1])


def fluxo_caixa(usuario_id: str, ano_mes: str) -> dict:
    conn = get_connection()
    try:
        entrou_mes = _soma_entrou(conn, usuario_id, ano_mes)
        saiu_mes = _soma_gastos(conn, usuario_id, ano_mes)
        entrou_total = _soma_entrou(conn, usuario_id)
        saiu_total = _soma_gastos(conn, usuario_id)
    finally:
        conn.close()

    return {
        "ano_mes": ano_mes,
        "mes": _bloco_fluxo(entrou_mes, saiu_mes),
        "total_geral": _bloco_fluxo(entrou_total, saiu_total),
    }


def _query_compras_recorrentes(
    conn, usuario_id: str, ano_mes: str | None, limite: int
) -> list[dict]:
    params: list = [usuario_id]
    filtro_mes = ""
    if ano_mes:
        filtro_mes = "AND TO_CHAR(t.data_compra, 'YYYY-MM') = %s"
        params.append(ano_mes)
    params.append(limite)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                LOWER(TRIM(t.descricao)) AS descricao_chave,
                MIN(t.descricao) AS descricao,
                t.categoria_id,
                c.nome AS categoria_nome,
                COUNT(*) AS ocorrencias,
                COALESCE(SUM(t.valor), 0) AS total,
                COALESCE(AVG(t.valor), 0) AS media
            FROM transacoes t
            JOIN categorias c ON c.id = t.categoria_id
            WHERE t.usuario_id = %s
              {filtro_mes}
            GROUP BY LOWER(TRIM(t.descricao)), t.categoria_id, c.nome
            HAVING COUNT(*) >= 2
            ORDER BY total DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [
            {
                "descricao": row[1],
                "categoria_id": row[2],
                "categoria_nome": row[3],
                "ocorrencias": row[4],
                "total": row[5],
                "media": row[6],
            }
            for row in cur.fetchall()
        ]


def compras_recorrentes(usuario_id: str, ano_mes: str, limite: int = 10) -> dict:
    conn = get_connection()
    try:
        mes = _query_compras_recorrentes(conn, usuario_id, ano_mes, limite)
        total_geral = _query_compras_recorrentes(conn, usuario_id, None, limite)
    finally:
        conn.close()

    return {
        "ano_mes": ano_mes,
        "mes": mes,
        "total_geral": total_geral,
    }


def _query_categorias_top(
    conn, usuario_id: str, ano_mes: str | None, limite: int
) -> list[dict]:
    params: list = [usuario_id]
    filtro_mes = ""
    if ano_mes:
        filtro_mes = "AND TO_CHAR(t.data_compra, 'YYYY-MM') = %s"
        params.append(ano_mes)
    params.append(limite)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                t.categoria_id,
                c.nome AS categoria_nome,
                COALESCE(SUM(t.valor), 0) AS total,
                COUNT(*) AS qtd
            FROM transacoes t
            JOIN categorias c ON c.id = t.categoria_id
            WHERE t.usuario_id = %s
              {filtro_mes}
            GROUP BY t.categoria_id, c.nome
            ORDER BY total DESC
            LIMIT %s
            """,
            tuple(params),
        )
        rows = cur.fetchall()

    soma_total = sum(_decimal(row[2]) for row in rows) or Decimal("0")
    resultado = []
    for row in rows:
        total = _decimal(row[2])
        percentual = None
        if soma_total > 0:
            percentual = (total / soma_total * 100).quantize(Decimal("0.01"))
        resultado.append(
            {
                "categoria_id": row[0],
                "categoria_nome": row[1],
                "total": total,
                "qtd": row[3],
                "percentual": percentual,
            }
        )
    return resultado


def categorias_top(usuario_id: str, ano_mes: str, limite: int = 10) -> dict:
    conn = get_connection()
    try:
        mes = _query_categorias_top(conn, usuario_id, ano_mes, limite)
        total_geral = _query_categorias_top(conn, usuario_id, None, limite)
    finally:
        conn.close()

    return {
        "ano_mes": ano_mes,
        "mes": mes,
        "total_geral": total_geral,
    }


def patrimonio_evolucao(usuario_id: str) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ano_mes,
                    renda,
                    investimento,
                    rendimentos,
                    patrimonio,
                    patrimonio_sugerido,
                    COALESCE(patrimonio, patrimonio_sugerido) AS patrimonio_efetivo
                FROM resumo_mensal
                WHERE usuario_id = %s
                ORDER BY ano_mes ASC
                """,
                (usuario_id,),
            )
            serie = [
                {
                    "ano_mes": row[0],
                    "renda": row[1],
                    "investimento": row[2],
                    "rendimentos": row[3],
                    "patrimonio": row[4],
                    "patrimonio_sugerido": row[5],
                    "patrimonio_efetivo": row[6],
                }
                for row in cur.fetchall()
            ]
    finally:
        conn.close()

    return {"serie": serie}


def orcamentos_resumo(usuario_id: str, ano_mes: str) -> dict:
    por_categoria = status_por_mes(usuario_id, ano_mes)
    total_planejado = sum(
        (item["valor_planejado"] for item in por_categoria), Decimal("0")
    )
    total_gasto = sum((item["valor_gasto"] for item in por_categoria), Decimal("0"))
    saldo_restante = total_planejado - total_gasto

    return {
        "ano_mes": ano_mes,
        "totais": {
            "valor_planejado": total_planejado,
            "valor_gasto": total_gasto,
            "saldo_restante": saldo_restante,
            "percentual_usado": _calcular_percentual(total_gasto, total_planejado),
        },
        "por_categoria": por_categoria,
    }
