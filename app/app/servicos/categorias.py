import unicodedata

from app.servicos.db import get_connection


def _normalizar_nome(nome: str) -> str:
    texto = nome.strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def listar_ativas() -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome
                FROM categorias
                WHERE ativa = TRUE
                ORDER BY nome
                """
            )
            return [{"id": row[0], "nome": row[1]} for row in cur.fetchall()]
    finally:
        conn.close()


def categoria_ativa_existe(categoria_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM categorias
                WHERE id = %s AND ativa = TRUE
                """,
                (categoria_id,),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def mapa_nome_para_id() -> dict[str, int]:
    return {_normalizar_nome(cat["nome"]): cat["id"] for cat in listar_ativas()}
