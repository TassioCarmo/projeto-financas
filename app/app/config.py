import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://financas:financas@localhost:5432/financas_db",
    )
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
