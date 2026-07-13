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


def _obter_categoria_por_nome(nome: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categorias WHERE nome = %s AND ativa = TRUE",
                (nome,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _cadastrar_transacao(client, data_compra, descricao, categoria_id, valor, pago=False):
    client.post(
        "/transacoes",
        data={
            "data_compra": data_compra,
            "descricao": descricao,
            "categoria_id": str(categoria_id),
            "valor": str(valor),
            "pago": "true" if pago else "",
        },
        follow_redirects=True,
    )


def test_filtros_listagem(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    cat_alimentacao = _obter_categoria_por_nome("Alimentação")
    cat_transporte = _obter_categoria_por_nome("Transporte")

    # jul/2026 pago (Alimentação)
    _cadastrar_transacao(
        client, "2026-07-10", "Supermercado jul pago", cat_alimentacao, "100.00", pago=True
    )
    # jul/2026 não pago (Transporte)
    _cadastrar_transacao(
        client, "2026-07-15", "Uber jul nao pago", cat_transporte, "50.00", pago=False
    )
    # jun/2026 pago (Alimentação)
    _cadastrar_transacao(
        client, "2026-06-20", "Mercado jun pago", cat_alimentacao, "80.00", pago=True
    )

    # Sem filtros: 3 transações
    response = client.get("/transacoes")
    assert response.status_code == 200
    assert b"Supermercado jul pago" in response.data
    assert b"Uber jul nao pago" in response.data
    assert b"Mercado jun pago" in response.data

    # Filtro por intervalo de datas (julho)
    response = client.get("/transacoes?data_inicio=2026-07-01&data_fim=2026-07-31")
    assert b"Supermercado jul pago" in response.data
    assert b"Uber jul nao pago" in response.data
    assert b"Mercado jun pago" not in response.data

    # Filtro por pago = true
    response = client.get("/transacoes?pago=true")
    assert b"Supermercado jul pago" in response.data
    assert b"Mercado jun pago" in response.data
    assert b"Uber jul nao pago" not in response.data

    # Combinação: categoria + pago=false
    response = client.get(
        f"/transacoes?categoria_id={cat_transporte}&pago=false"
    )
    assert b"Uber jul nao pago" in response.data
    assert b"Supermercado jul pago" not in response.data
    assert b"Mercado jun pago" not in response.data

    # JSON com filtros
    response = client.get(
        "/transacoes?data_inicio=2026-07-01&data_fim=2026-07-31&pago=true",
        headers={"Accept": "application/json"},
    )
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["descricao"] == "Supermercado jul pago"


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
