import psycopg2

from app.config import Config


def get_connection():
    return psycopg2.connect(Config.DATABASE_URL)


def check_db() -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    finally:
        conn.close()
