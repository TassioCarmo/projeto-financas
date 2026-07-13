"""
Serviço de resumo mensal — renda, investimento, rendimentos e patrimônio.

Cada usuário pode ter um registro por mês (chave: usuario_id + ano_mes).
O patrimonio_sugerido é calculado automaticamente; o patrimonio manual
só muda quando o usuário informa no formulário.
"""

from decimal import Decimal

from app.servicos.db import get_connection


def _row_to_dict(row) -> dict:
    """Converte uma linha do banco (tupla) em dicionário Python."""
    return {
        "id": row[0],
        "ano_mes": row[1],
        "renda": row[2],
        "investimento": row[3],
        "rendimentos": row[4],
        "patrimonio": row[5],
        "patrimonio_sugerido": row[6],
        "criado_em": row[7],
        "atualizado_em": row[8],
    }


def _mes_anterior(ano_mes: str) -> str | None:
    """
    Retorna o mês anterior no formato "AAAA-MM".

    Exemplos:
        "2026-03" -> "2026-02"
        "2026-01" -> None  (janeiro não tem mês anterior no mesmo ano)
    """
    ano_str, mes_str = ano_mes.split("-")
    ano = int(ano_str)
    mes = int(mes_str)

    if mes == 1:
        # Janeiro: não buscamos dezembro do ano anterior nesta fase
        return None

    return f"{ano}-{mes - 1:02d}"


def _buscar_por_mes(usuario_id: str, ano_mes: str) -> dict | None:
    """Busca um registro específico de um usuário. Retorna None se não existir."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, ano_mes, renda, investimento, rendimentos,
                    patrimonio, patrimonio_sugerido, criado_em, atualizado_em
                FROM resumo_mensal
                WHERE usuario_id = %s AND ano_mes = %s
                """,
                (usuario_id, ano_mes),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    finally:
        conn.close()


def _calcular_patrimonio_sugerido(
    usuario_id: str,
    ano_mes: str,
    investimento: Decimal,
    rendimentos: Decimal,
) -> Decimal:
    """
    Calcula o patrimônio sugerido (acumulado) para o mês.

    Passos:
    1. Descobre qual é o mês anterior (ex: fev/2026 para mar/2026)
    2. Busca o registro do mês anterior
    3. Define a "base":
       - Se o mês anterior tem patrimonio manual → usa ele
       - Senão, se tem patrimonio_sugerido → usa ele
       - Senão → 0
    4. patrimonio_sugerido = base + investimento + rendimentos

    A renda NÃO entra neste cálculo (fica só para histórico).
    """
    mes_ant = _mes_anterior(ano_mes)
    base = Decimal("0")

    if mes_ant:
        registro_anterior = _buscar_por_mes(usuario_id, mes_ant)
        if registro_anterior:
            # Prioridade: patrimonio manual > patrimonio_sugerido > 0
            if registro_anterior["patrimonio"] is not None:
                base = registro_anterior["patrimonio"]
            elif registro_anterior["patrimonio_sugerido"] is not None:
                base = registro_anterior["patrimonio_sugerido"]

    return base + investimento + rendimentos


def salvar_resumo(
    usuario_id: str,
    ano_mes: str,
    renda: Decimal,
    investimento: Decimal,
    rendimentos: Decimal,
    patrimonio: Decimal | None,
) -> dict:
    """
    Cria ou atualiza o resumo de um mês (upsert).

    Se já existir registro para usuario_id + ano_mes, atualiza.
    Se patrimonio vier None, mantém o valor manual já salvo (no update).
    patrimonio_sugerido é sempre recalculado.
    """
    patrimonio_sugerido = _calcular_patrimonio_sugerido(
        usuario_id, ano_mes, investimento, rendimentos
    )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ON CONFLICT = se já existe (usuario_id, ano_mes), faz UPDATE em vez de INSERT
            cur.execute(
                """
                INSERT INTO resumo_mensal (
                    usuario_id, ano_mes, renda, investimento, rendimentos,
                    patrimonio, patrimonio_sugerido
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (usuario_id, ano_mes) DO UPDATE SET
                    renda = EXCLUDED.renda,
                    investimento = EXCLUDED.investimento,
                    rendimentos = EXCLUDED.rendimentos,
                    -- COALESCE: se patrimonio novo for NULL, mantém o antigo
                    patrimonio = COALESCE(EXCLUDED.patrimonio, resumo_mensal.patrimonio),
                    patrimonio_sugerido = EXCLUDED.patrimonio_sugerido,
                    atualizado_em = NOW()
                RETURNING id
                """,
                (
                    usuario_id,
                    ano_mes,
                    renda,
                    investimento,
                    rendimentos,
                    patrimonio,
                    patrimonio_sugerido,
                ),
            )
            conn.commit()

        # Retorna o registro completo após salvar
        registro = _buscar_por_mes(usuario_id, ano_mes)
        assert registro is not None
        return registro
    finally:
        conn.close()


def listar_por_ano(usuario_id: str, ano: int) -> list[dict]:
    """
    Lista todos os resumos de um ano para o usuário.

    Ex: ano=2026 retorna registros com ano_mes começando em "2026-".
    Ordenado do mês mais antigo para o mais recente.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, ano_mes, renda, investimento, rendimentos,
                    patrimonio, patrimonio_sugerido, criado_em, atualizado_em
                FROM resumo_mensal
                WHERE usuario_id = %s AND ano_mes LIKE %s
                ORDER BY ano_mes ASC
                """,
                (usuario_id, f"{ano}-%"),
            )
            return [_row_to_dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
