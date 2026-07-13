import pytest

from app import create_app
from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations


pytestmark = pytest.mark.integration

EMAIL_A = "transacoes-a@example.com"
EMAIL_B = "transacoes-b@example.com"
SENHA = "senha123"
NOME_A = "Usuário A"
NOME_B = "Usuário B"


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


def _limpar_usuarios():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM usuarios WHERE email IN (%s, %s)",
                (EMAIL_A, EMAIL_B),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def cleanup():
    _limpar_usuarios()
    yield
    _limpar_usuarios()


def _cadastrar_e_logar(client, nome, email):
    client.post(
        "/auth/cadastro",
        data={"nome": nome, "email": email, "senha": SENHA},
    )
    return client.post(
        "/auth/login",
        data={"email": email, "senha": SENHA},
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


def test_fluxo_completo_transacoes(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_id()

    response = client.post(
        "/transacoes",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Almoço no restaurante",
            "categoria_id": str(categoria_id),
            "valor": "45.90",
            "pago": "true",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Almo" in response.data

    response = client.get("/transacoes")
    assert response.status_code == 200
    assert b"45.90" in response.data

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id FROM transacoes t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE u.email = %s
                """,
                (EMAIL_A,),
            )
            transacao_id = cur.fetchone()[0]
    finally:
        conn.close()

    response = client.put(
        f"/transacoes/{transacao_id}",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Jantar atualizado",
            "categoria_id": str(categoria_id),
            "valor": "60.00",
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200

    response = client.get("/transacoes")
    assert b"Jantar atualizado" in response.data
    assert b"60.00" in response.data

    response = client.delete(
        f"/transacoes/{transacao_id}",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 204

    response = client.get("/transacoes")
    assert b"Jantar atualizado" not in response.data
    assert b"Nenhuma transa" in response.data


def test_isolamento_entre_usuarios(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_id()

    client.post(
        "/transacoes",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Gasto do usuário A",
            "categoria_id": str(categoria_id),
            "valor": "30.00",
        },
        follow_redirects=True,
    )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id FROM transacoes t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE u.email = %s
                """,
                (EMAIL_A,),
            )
            transacao_id = cur.fetchone()[0]
    finally:
        conn.close()

    client.post("/auth/logout", follow_redirects=True)
    _cadastrar_e_logar(client, NOME_B, EMAIL_B)

    response = client.put(
        f"/transacoes/{transacao_id}",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Tentativa de edição",
            "categoria_id": str(categoria_id),
            "valor": "99.00",
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 404

    response = client.delete(
        f"/transacoes/{transacao_id}",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 404

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT descricao FROM transacoes WHERE id = %s", (transacao_id,))
            assert cur.fetchone()[0] == "Gasto do usuário A"
    finally:
        conn.close()
