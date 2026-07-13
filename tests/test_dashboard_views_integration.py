import pytest

from app import create_app
from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations

pytestmark = pytest.mark.integration

EMAIL_A = "dashboard-views-a@example.com"
EMAIL_B = "dashboard-views-b@example.com"
SENHA = "senha123"
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


def _cadastrar_e_logar(client, email, nome):
    client.post(
        "/auth/cadastro",
        data={"nome": nome, "email": email, "senha": SENHA},
    )
    return client.post(
        "/auth/login",
        data={"email": email, "senha": SENHA},
        follow_redirects=True,
    )


def _obter_categoria(nome):
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


def _setup_usuario_a(client):
    _cadastrar_e_logar(client, EMAIL_A, "Usuário A")
    cat = _obter_categoria("Alimentação")
    client.post(
        "/resumo-mensal",
        data={
            "ano_mes": ANO_MES,
            "renda": "5000",
            "investimento": "500",
            "rendimentos": "120",
        },
        follow_redirects=True,
    )
    client.post(
        "/transacoes",
        data={
            "data_compra": "2026-07-10",
            "descricao": "Mercado dashboard A",
            "categoria_id": str(cat),
            "valor": "250.00",
        },
        follow_redirects=True,
    )
    client.post(
        "/orcamentos",
        data={
            "ano_mes": ANO_MES,
            "categoria_id": str(cat),
            "valor_planejado": "1000",
        },
        follow_redirects=True,
    )


def test_dashboard_html_carrega_com_dados_reais_via_api(client):
    _setup_usuario_a(client)

    response = client.get(f"/dashboard?ano_mes={ANO_MES}")
    assert response.status_code == 200
    assert b"chart-fluxo" in response.data
    assert b"fluxo-caixa" in response.data
    assert ANO_MES.encode() in response.data

    api = client.get(f"/dashboard/fluxo-caixa?ano_mes={ANO_MES}")
    dados = api.get_json()
    assert dados["mes"]["entrou"] == 5120.0
    assert dados["mes"]["saiu"] == 250.0


def test_isolamento_dashboard_html_e_api(client):
    _setup_usuario_a(client)
    api_a = client.get(f"/dashboard/fluxo-caixa?ano_mes={ANO_MES}")
    assert api_a.get_json()["mes"]["saiu"] == 250.0

    client.post("/auth/logout", follow_redirects=True)
    _cadastrar_e_logar(client, EMAIL_B, "Usuário B")

    api_b = client.get(f"/dashboard/fluxo-caixa?ano_mes={ANO_MES}")
    assert api_b.get_json()["mes"]["saiu"] == 0.0

    response = client.get(f"/dashboard?ano_mes={ANO_MES}")
    assert response.status_code == 200
    assert b"Mercado dashboard A" not in response.data


def test_subnav_navegavel_com_ano_mes(client):
    _setup_usuario_a(client)
    response = client.get(f"/dashboard/categorias?ano_mes={ANO_MES}")
    assert response.status_code == 200
    assert b"/dashboard/recorrencias?ano_mes=2026-07" in response.data
    assert b"/consultas" in response.data


def test_consultas_integrada_na_subnav(client):
    _setup_usuario_a(client)
    response = client.get("/consultas")
    assert response.status_code == 200
    assert b"subnav" in response.data or b"Vis" in response.data
    assert b"/dashboard" in response.data
    assert b"Consultas" in response.data
