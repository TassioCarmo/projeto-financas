import bcrypt
import psycopg2

from app.servicos.db import get_connection


class EmailJaCadastradoError(Exception):
    pass


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))


def criar_usuario(nome: str, email: str, senha: str) -> dict:
    senha_hash = hash_senha(senha)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usuarios (nome, email, senha_hash)
                VALUES (%s, %s, %s)
                RETURNING id, nome, email
                """,
                (nome, email, senha_hash),
            )
            row = cur.fetchone()
            conn.commit()
            return {"id": row[0], "nome": row[1], "email": row[2]}
    except psycopg2.IntegrityError as exc:
        conn.rollback()
        if "usuarios_email_key" in str(exc) or "unique" in str(exc).lower():
            raise EmailJaCadastradoError("Email já cadastrado") from exc
        raise
    finally:
        conn.close()


def buscar_por_email(email: str) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, email, senha_hash
                FROM usuarios
                WHERE email = %s
                """,
                (email,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "nome": row[1],
                "email": row[2],
                "senha_hash": row[3],
            }
    finally:
        conn.close()
