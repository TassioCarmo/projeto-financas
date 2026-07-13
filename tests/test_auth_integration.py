import pytest

from app import create_app
from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations


pytestmark = pytest.mark.integration

TEST_EMAIL = "teste-auth@example.com"
TEST_SENHA = "senha123"
TEST_NOME = "Usuário Teste"


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


def _limpar_usuario_teste():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE email = %s", (TEST_EMAIL,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def cleanup():
    _limpar_usuario_teste()
    yield
    _limpar_usuario_teste()


def test_fluxo_completo_auth(client):
    response = client.post(
        "/auth/cadastro",
        data={"nome": TEST_NOME, "email": TEST_EMAIL, "senha": TEST_SENHA},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM usuarios WHERE email = %s", (TEST_EMAIL,))
            row = cur.fetchone()
            assert row is not None
            assert row[1] == TEST_NOME
    finally:
        conn.close()

    response = client.get("/perfil", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    response = client.post(
        "/auth/login",
        data={"email": TEST_EMAIL, "senha": TEST_SENHA},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/perfil")

    response = client.get("/perfil")
    assert response.status_code == 200
    assert TEST_NOME.encode() in response.data
    assert TEST_EMAIL.encode() in response.data

    response = client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    response = client.get("/perfil", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_cadastro_email_duplicado(client):
    client.post(
        "/auth/cadastro",
        data={"nome": TEST_NOME, "email": TEST_EMAIL, "senha": TEST_SENHA},
    )
    response = client.post(
        "/auth/cadastro",
        data={"nome": "Outro", "email": TEST_EMAIL, "senha": "outrasenha"},
    )
    assert response.status_code == 200
    assert b"Email j" in response.data
