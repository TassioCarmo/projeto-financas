from datetime import date
from decimal import Decimal

from app.servicos.categorias import categoria_ativa_existe
from app.servicos.db import get_connection


class TransacaoNaoEncontradaError(Exception):
    pass


class CategoriaInvalidaError(Exception):
    pass


def _row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "data_compra": row[1],
        "descricao": row[2],
        "categoria_id": row[3],
        "categoria_nome": row[4],
        "valor": row[5],
        "pago": row[6],
        "pago_por_terceiro": row[7],
        "nome_terceiro": row[8],
        "origem": row[9],
        "criado_em": row[10],
        "atualizado_em": row[11],
    }


def _validar_categoria(categoria_id: int) -> None:
    if not categoria_ativa_existe(categoria_id):
        raise CategoriaInvalidaError("Categoria inválida.")


def criar_transacao(
    usuario_id: str,
    data_compra: date,
    descricao: str,
    categoria_id: int,
    valor: Decimal,
    pago: bool,
    pago_por_terceiro: bool,
    nome_terceiro: str | None,
    origem: str = "manual",
) -> dict:
    if origem not in ("manual", "importacao"):
        raise ValueError("Origem inválida.")
    _validar_categoria(categoria_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transacoes (
                    usuario_id, data_compra, descricao, categoria_id, valor,
                    pago, pago_por_terceiro, nome_terceiro, origem
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    usuario_id,
                    data_compra,
                    descricao,
                    categoria_id,
                    valor,
                    pago,
                    pago_por_terceiro,
                    nome_terceiro,
                    origem,
                ),
            )
            transacao_id = cur.fetchone()[0]
            conn.commit()
            transacao = buscar_por_id(usuario_id, transacao_id)
            assert transacao is not None
            return transacao
    finally:
        conn.close()


def listar_por_usuario(usuario_id: str) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    t.id, t.data_compra, t.descricao, t.categoria_id, c.nome,
                    t.valor, t.pago, t.pago_por_terceiro, t.nome_terceiro,
                    t.origem, t.criado_em, t.atualizado_em
                FROM transacoes t
                JOIN categorias c ON c.id = t.categoria_id
                WHERE t.usuario_id = %s
                ORDER BY t.data_compra DESC, t.id DESC
                """,
                (usuario_id,),
            )
            return [_row_to_dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def buscar_por_id(usuario_id: str, transacao_id: int) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    t.id, t.data_compra, t.descricao, t.categoria_id, c.nome,
                    t.valor, t.pago, t.pago_por_terceiro, t.nome_terceiro,
                    t.origem, t.criado_em, t.atualizado_em
                FROM transacoes t
                JOIN categorias c ON c.id = t.categoria_id
                WHERE t.id = %s AND t.usuario_id = %s
                """,
                (transacao_id, usuario_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_dict(row)
    finally:
        conn.close()


def atualizar_transacao(
    usuario_id: str,
    transacao_id: int,
    data_compra: date,
    descricao: str,
    categoria_id: int,
    valor: Decimal,
    pago: bool,
    pago_por_terceiro: bool,
    nome_terceiro: str | None,
) -> dict:
    _validar_categoria(categoria_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE transacoes
                SET data_compra = %s,
                    descricao = %s,
                    categoria_id = %s,
                    valor = %s,
                    pago = %s,
                    pago_por_terceiro = %s,
                    nome_terceiro = %s,
                    atualizado_em = NOW()
                WHERE id = %s AND usuario_id = %s
                """,
                (
                    data_compra,
                    descricao,
                    categoria_id,
                    valor,
                    pago,
                    pago_por_terceiro,
                    nome_terceiro,
                    transacao_id,
                    usuario_id,
                ),
            )
            if cur.rowcount == 0:
                conn.rollback()
                raise TransacaoNaoEncontradaError("Transação não encontrada.")
            conn.commit()
            transacao = buscar_por_id(usuario_id, transacao_id)
            assert transacao is not None
            return transacao
    finally:
        conn.close()


def excluir_transacao(usuario_id: str, transacao_id: int) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM transacoes
                WHERE id = %s AND usuario_id = %s
                """,
                (transacao_id, usuario_id),
            )
            if cur.rowcount == 0:
                conn.rollback()
                raise TransacaoNaoEncontradaError("Transação não encontrada.")
            conn.commit()
    finally:
        conn.close()
