import pytest

from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations


pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def migrated_db():
    run_migrations()
    return True


def _table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,),
    )
    return cur.fetchone()[0]


def _index_exists(cur, index_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public' AND indexname = %s
        )
        """,
        (index_name,),
    )
    return cur.fetchone()[0]


def _foreign_key_exists(cur, table_name: str, referenced_table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = %s
              AND ccu.table_name = %s
        )
        """,
        (table_name, referenced_table),
    )
    return cur.fetchone()[0]


def test_tables_exist(migrated_db):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for table in (
                "usuarios",
                "categorias",
                "transacoes",
                "resumo_mensal",
                "orcamentos",
                "schema_migrations",
            ):
                assert _table_exists(cur, table), f"Tabela {table} não encontrada"
    finally:
        conn.close()


def test_categorias_seed(migrated_db):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM categorias WHERE ativa = TRUE")
            count = cur.fetchone()[0]
            assert count == 11
    finally:
        conn.close()


def test_transacoes_foreign_keys(migrated_db):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            assert _foreign_key_exists(cur, "transacoes", "usuarios")
            assert _foreign_key_exists(cur, "transacoes", "categorias")
    finally:
        conn.close()


def test_transacoes_usuario_id_index(migrated_db):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            assert _index_exists(cur, "idx_transacoes_usuario_id")
    finally:
        conn.close()


def test_resumo_mensal_foreign_key(migrated_db):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            assert _foreign_key_exists(cur, "resumo_mensal", "usuarios")
    finally:
        conn.close()


def test_resumo_mensal_usuario_ano_index(migrated_db):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            assert _index_exists(cur, "idx_resumo_mensal_usuario_ano")
    finally:
        conn.close()


def test_orcamentos_foreign_keys(migrated_db):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            assert _foreign_key_exists(cur, "orcamentos", "usuarios")
            assert _foreign_key_exists(cur, "orcamentos", "categorias")
    finally:
        conn.close()


def test_orcamentos_usuario_mes_index(migrated_db):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            assert _index_exists(cur, "idx_orcamentos_usuario_mes")
    finally:
        conn.close()


def test_migrations_are_idempotent(migrated_db):
    applied = run_migrations()
    assert applied == []
