from pathlib import Path

import pytest

from app import create_app
from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations

pytestmark = pytest.mark.integration

EMAIL = "importacao@example.com"
SENHA = "senha123"
NOME = "Usuário Importação"
FIXTURE = Path(__file__).parent / "fixtures" / "planilha_exemplo.csv"
FIXTURE_EXTRATO = Path(__file__).parent / "fixtures" / "extrato_bancario_exemplo.csv"


@pytest.fixture(scope="session")
def migrated_db():
    run_migrations()
    return True


@pytest.fixture
def client(migrated_db):
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    with app.test_client() as client:
        yield client


def _limpar_usuario():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def cleanup():
    _limpar_usuario()
    yield
    _limpar_usuario()


def _cadastrar_e_logar(client):
    client.post(
        "/auth/cadastro",
        data={"nome": NOME, "email": EMAIL, "senha": SENHA},
    )
    return client.post(
        "/auth/login",
        data={"email": EMAIL, "senha": SENHA},
        follow_redirects=True,
    )


def _obter_categoria_id():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM categorias WHERE ativa = TRUE LIMIT 1")
            return cur.fetchone()[0]
    finally:
        conn.close()


def test_fluxo_importacao_planilha(client):
    _cadastrar_e_logar(client)
    categoria_id = _obter_categoria_id()

    response = client.post(
        "/transacoes",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Gasto manual",
            "categoria_id": str(categoria_id),
            "valor": "50.00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Gasto manual" in response.data

    with FIXTURE.open("rb") as arquivo:
        response = client.post(
            "/transacoes/importar",
            data={"arquivo": (arquivo, "planilha_exemplo.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"2 transa" in response.data.lower()
    assert b"1 linha" in response.data.lower() or b"1 linha(s)" in response.data.lower()
    assert b"Supermercado" in response.data
    assert b"Uber" in response.data
    assert b"Gasto manual" in response.data

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM transacoes t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE u.email = %s AND t.origem = 'importacao'
                """,
                (EMAIL,),
            )
            assert cur.fetchone()[0] == 2
    finally:
        conn.close()


def test_fluxo_importacao_extrato_bancario(client):
    _cadastrar_e_logar(client)

    with FIXTURE_EXTRATO.open("rb") as arquivo:
        response = client.post(
            "/transacoes/importar",
            data={
                "arquivo": (arquivo, "extrato_bancario_exemplo.csv"),
                "perfil": "extrato_bancario",
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"2 transa" in response.data.lower()
    assert b"PIX SUPERMERCADO" in response.data
    assert b"UBER TRIP" in response.data
    assert b"Extrato banc" in response.data or b"extrato_bancario" in response.data

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM transacoes t
                JOIN usuarios u ON u.id = t.usuario_id
                JOIN categorias c ON c.id = t.categoria_id
                WHERE u.email = %s
                  AND t.origem = 'importacao'
                  AND c.nome = 'Outros'
                """,
                (EMAIL,),
            )
            assert cur.fetchone()[0] == 2
    finally:
        conn.close()


def test_fluxo_importacao_extrato_auto_detect(client):
    _cadastrar_e_logar(client)

    with FIXTURE_EXTRATO.open("rb") as arquivo:
        response = client.post(
            "/transacoes/importar",
            data={"arquivo": (arquivo, "extrato_bancario_exemplo.csv"), "perfil": "auto"},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"2 transa" in response.data.lower()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM transacoes t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE u.email = %s AND t.origem = 'importacao'
                """,
                (EMAIL,),
            )
            assert cur.fetchone()[0] == 2
    finally:
        conn.close()
