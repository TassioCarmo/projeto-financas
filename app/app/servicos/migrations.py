from pathlib import Path

from app.servicos.db import get_connection

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _ensure_migrations_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            versao TEXT PRIMARY KEY,
            aplicado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _get_applied_versions(cur) -> set[str]:
    cur.execute("SELECT versao FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def _list_sql_files() -> list[Path]:
    return sorted(SQL_DIR.glob("*.sql"))


def run_migrations() -> list[str]:
    sql_files = _list_sql_files()
    if not sql_files:
        return []

    conn = get_connection()
    applied: list[str] = []

    try:
        with conn.cursor() as cur:
            _ensure_migrations_table(cur)
        conn.commit()

        applied_versions = set()
        with conn.cursor() as cur:
            applied_versions = _get_applied_versions(cur)

        for sql_file in sql_files:
            version = sql_file.name
            if version in applied_versions:
                continue

            sql = sql_file.read_text(encoding="utf-8")
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (versao) VALUES (%s)",
                        (version,),
                    )
            applied.append(version)
    finally:
        conn.close()

    return applied
