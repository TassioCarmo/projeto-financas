import pytest

from app import create_app
from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations


pytestmark = pytest.mark.integration

EMAIL_A = "orcamentos-a@example.com"
EMAIL_B = "orcamentos-b@example.com"
SENHA = "senha123"
NOME_A = "Usuário A"
NOME_B = "Usuário B"
ANO_MES = "2026-07"


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


def _obter_categoria_alimentacao():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categorias WHERE nome = 'Alimentação' AND ativa = TRUE"
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _contar_orcamentos(email):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM orcamentos o
                JOIN usuarios u ON u.id = o.usuario_id
                WHERE u.email = %s
                """,
                (email,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def test_fluxo_completo_orcamentos(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_alimentacao()

    # 1. Criar orçamento R$ 500 para Alimentação em jul/2026
    response = client.post(
        "/orcamentos",
        data={
            "ano_mes": ANO_MES,
            "categoria_id": str(categoria_id),
            "valor_planejado": "500",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Alimenta" in response.data or b"500" in response.data

    # Status sem gastos: 0% usado
    response = client.get(
        f"/orcamentos/{ANO_MES}/status",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["valor_planejado"] == 500.0
    assert data[0]["valor_gasto"] == 0.0
    assert data[0]["percentual_usado"] == 0.0
    assert data[0]["saldo_restante"] == 500.0

    # 2. Cadastrar gasto R$ 150 na mesma categoria/mês
    client.post(
        "/transacoes",
        data={
            "data_compra": "2026-07-15",
            "descricao": "Supermercado",
            "categoria_id": str(categoria_id),
            "valor": "150",
            "pago": "true",
        },
        follow_redirects=True,
    )

    # Status deve mostrar 30% usado
    response = client.get(
        f"/orcamentos/{ANO_MES}/status",
        headers={"Accept": "application/json"},
    )
    data = response.get_json()
    assert data[0]["valor_gasto"] == 150.0
    assert data[0]["percentual_usado"] == 30.0
    assert data[0]["saldo_restante"] == 350.0

    # 3. Upsert: reenviar mesmo orçamento com R$ 400
    client.post(
        "/orcamentos",
        data={
            "ano_mes": ANO_MES,
            "categoria_id": str(categoria_id),
            "valor_planejado": "400",
        },
        follow_redirects=True,
    )
    assert _contar_orcamentos(EMAIL_A) == 1

    response = client.get(
        f"/orcamentos/{ANO_MES}/status",
        headers={"Accept": "application/json"},
    )
    data = response.get_json()
    assert data[0]["valor_planejado"] == 400.0
    assert data[0]["percentual_usado"] == 37.5  # 150/400 * 100
    assert data[0]["saldo_restante"] == 250.0


def test_gasto_fora_do_mes_nao_conta(client):
    """Transação de outro mês não entra no cálculo de gasto real."""
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_alimentacao()

    client.post(
        "/orcamentos",
        data={
            "ano_mes": ANO_MES,
            "categoria_id": str(categoria_id),
            "valor_planejado": "500",
        },
        follow_redirects=True,
    )

    # Gasto em junho (mês diferente)
    client.post(
        "/transacoes",
        data={
            "data_compra": "2026-06-20",
            "descricao": "Compra antiga",
            "categoria_id": str(categoria_id),
            "valor": "200",
        },
        follow_redirects=True,
    )

    response = client.get(
        f"/orcamentos/{ANO_MES}/status",
        headers={"Accept": "application/json"},
    )
    data = response.get_json()
    assert data[0]["valor_gasto"] == 0.0


def test_isolamento_entre_usuarios(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_alimentacao()

    client.post(
        "/orcamentos",
        data={
            "ano_mes": ANO_MES,
            "categoria_id": str(categoria_id),
            "valor_planejado": "500",
        },
        follow_redirects=True,
    )

    client.post("/auth/logout", follow_redirects=True)
    _cadastrar_e_logar(client, NOME_B, EMAIL_B)

    response = client.get(f"/orcamentos?ano_mes={ANO_MES}")
    assert response.status_code == 200
    assert b"Nenhum or" in response.data

    response = client.get(
        f"/orcamentos/{ANO_MES}/status",
        headers={"Accept": "application/json"},
    )
    assert response.get_json() == []

    assert _contar_orcamentos(EMAIL_B) == 0
    assert _contar_orcamentos(EMAIL_A) == 1
