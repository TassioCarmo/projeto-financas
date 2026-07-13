"""
Serviço de orçamentos — limite planejado de gasto por categoria e mês.

Cada usuário pode ter um orçamento por categoria + mês (chave: usuario_id + categoria_id + ano_mes).
O gasto real vem da soma das transações no mês (data_compra), sem filtrar pago/pago_por_terceiro.
"""

from decimal import Decimal, ROUND_HALF_UP

from app.servicos.categorias import categoria_ativa_existe
from app.servicos.db import get_connection


class CategoriaInvalidaError(Exception):
    pass


def _row_to_dict(row) -> dict:
    """Converte uma linha do banco (tupla) em dicionário Python."""
    return {
        "id": row[0],
        "categoria_id": row[1],
        "categoria_nome": row[2],
        "ano_mes": row[3],
        "valor_planejado": row[4],
        "criado_em": row[5],
        "atualizado_em": row[6],
    }


def _validar_categoria(categoria_id: int) -> None:
    if not categoria_ativa_existe(categoria_id):
        raise CategoriaInvalidaError("Categoria inválida.")


def _calcular_percentual(valor_gasto: Decimal, valor_planejado: Decimal) -> Decimal | None:
    """
    Calcula quanto % do orçamento já foi usado.

    Retorna None se valor_planejado for zero (evita divisão por zero).
    """
    if valor_planejado == 0:
        return None
    percentual = (valor_gasto / valor_planejado) * 100
    return percentual.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _buscar_por_chave(usuario_id: str, categoria_id: int, ano_mes: str) -> dict | None:
    """Busca um orçamento específico. Retorna None se não existir."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    o.id, o.categoria_id, c.nome, o.ano_mes,
                    o.valor_planejado, o.criado_em, o.atualizado_em
                FROM orcamentos o
                JOIN categorias c ON c.id = o.categoria_id
                WHERE o.usuario_id = %s AND o.categoria_id = %s AND o.ano_mes = %s
                """,
                (usuario_id, categoria_id, ano_mes),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    finally:
        conn.close()


def _gastos_por_categoria_no_mes(usuario_id: str, ano_mes: str) -> dict[int, Decimal]:
    """
    Soma o valor gasto por categoria no mês informado.

    Usa data_compra da transação para definir o mês.
    Inclui todas as transações (pago e pago_por_terceiro não filtram aqui).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT categoria_id, COALESCE(SUM(valor), 0)
                FROM transacoes
                WHERE usuario_id = %s
                  AND TO_CHAR(data_compra, 'YYYY-MM') = %s
                GROUP BY categoria_id
                """,
                (usuario_id, ano_mes),
            )
            return {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()


def salvar_orcamento(
    usuario_id: str,
    categoria_id: int,
    ano_mes: str,
    valor_planejado: Decimal,
) -> dict:
    """
    Cria ou atualiza um orçamento (upsert).

    Se já existir registro para usuario_id + categoria_id + ano_mes, atualiza o valor.
    """
    _validar_categoria(categoria_id)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ON CONFLICT = se já existe, faz UPDATE em vez de INSERT
            cur.execute(
                """
                INSERT INTO orcamentos (usuario_id, categoria_id, ano_mes, valor_planejado)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (usuario_id, categoria_id, ano_mes) DO UPDATE SET
                    valor_planejado = EXCLUDED.valor_planejado,
                    atualizado_em = NOW()
                RETURNING id
                """,
                (usuario_id, categoria_id, ano_mes, valor_planejado),
            )
            conn.commit()

        registro = _buscar_por_chave(usuario_id, categoria_id, ano_mes)
        assert registro is not None
        return registro
    finally:
        conn.close()


def status_por_mes(usuario_id: str, ano_mes: str) -> list[dict]:
    """
    Compara orçamento planejado vs. gasto real por categoria no mês.

    Retorna uma lista com:
    - valor_planejado: limite definido pelo usuário
    - valor_gasto: soma das transações no mês
    - saldo_restante: planejado - gasto (negativo = estourou o orçamento)
    - percentual_usado: (gasto / planejado) * 100, ou None se planejado = 0
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    o.id, o.categoria_id, c.nome, o.ano_mes,
                    o.valor_planejado, o.criado_em, o.atualizado_em
                FROM orcamentos o
                JOIN categorias c ON c.id = o.categoria_id
                WHERE o.usuario_id = %s AND o.ano_mes = %s
                ORDER BY c.nome ASC
                """,
                (usuario_id, ano_mes),
            )
            orcamentos = [_row_to_dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    gastos = _gastos_por_categoria_no_mes(usuario_id, ano_mes)

    resultado = []
    for orc in orcamentos:
        valor_gasto = gastos.get(orc["categoria_id"], Decimal("0"))
        valor_planejado = orc["valor_planejado"]
        saldo_restante = valor_planejado - valor_gasto

        resultado.append({
            "categoria_id": orc["categoria_id"],
            "categoria_nome": orc["categoria_nome"],
            "ano_mes": orc["ano_mes"],
            "valor_planejado": valor_planejado,
            "valor_gasto": valor_gasto,
            "saldo_restante": saldo_restante,
            "percentual_usado": _calcular_percentual(valor_gasto, valor_planejado),
        })

    return resultado
