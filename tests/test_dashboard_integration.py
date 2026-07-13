import pytest

from app import create_app
from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations

pytestmark = pytest.mark.integration

EMAIL = "dashboard@example.com"
SENHA = "senha123"
NOME = "Usuário Dashboard"
ANO_MES = "2026-07"
ANO_MES_ANT = "2026-06"


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


def _cadastrar_transacao(client, categoria_id, data, descricao, valor):
    client.post(
        "/transacoes",
        data={
            "data_compra": data,
            "descricao": descricao,
            "categoria_id": str(categoria_id),
            "valor": str(valor),
        },
        follow_redirects=True,
    )


def _salvar_resumo(client, ano_mes, renda, investimento, rendimentos, patrimonio=None):
    data = {
        "ano_mes": ano_mes,
        "renda": str(renda),
        "investimento": str(investimento),
        "rendimentos": str(rendimentos),
    }
    if patrimonio is not None:
        data["patrimonio"] = str(patrimonio)
    client.post("/resumo-mensal", data=data, follow_redirects=True)


def _setup_dados(client):
    _cadastrar_e_logar(client)
    cat_alimentacao = _obter_categoria("Alimentação")
    cat_transporte = _obter_categoria("Transporte")

    _salvar_resumo(client, ANO_MES, renda=5000, investimento=500, rendimentos=120)
    _salvar_resumo(client, ANO_MES_ANT, renda=4800, investimento=400, rendimentos=100)

    _cadastrar_transacao(client, cat_alimentacao, "2026-07-05", "Supermercado", 850)
    _cadastrar_transacao(client, cat_transporte, "2026-07-10", "Uber", 150)
    _cadastrar_transacao(client, cat_alimentacao, "2026-07-12", "Netflix", 50)
    _cadastrar_transacao(client, cat_alimentacao, "2026-07-20", "Netflix", 50)

    _cadastrar_transacao(client, cat_alimentacao, "2026-06-15", "Netflix", 50)
    _cadastrar_transacao(client, cat_alimentacao, "2026-06-20", "Netflix", 50)
    _cadastrar_transacao(client, cat_transporte, "2026-06-25", "Combustível", 200)

    client.post(
        "/orcamentos",
        data={
            "ano_mes": ANO_MES,
            "categoria_id": str(cat_alimentacao),
            "valor_planejado": "1000",
        },
        follow_redirects=True,
    )
    client.post(
        "/orcamentos",
        data={
            "ano_mes": ANO_MES,
            "categoria_id": str(cat_transporte),
            "valor_planejado": "300",
        },
        follow_redirects=True,
    )

    return cat_alimentacao, cat_transporte


def test_fluxo_caixa(client):
    _setup_dados(client)

    response = client.get(f"/dashboard/fluxo-caixa?ano_mes={ANO_MES}")
    assert response.status_code == 200
    data = response.get_json()

    assert data["mes"]["entrou"] == 5120.0
    assert data["mes"]["saiu"] == 1100.0
    assert data["mes"]["saldo"] == 4020.0
    assert data["total_geral"]["saiu"] == 1400.0


def test_compras_recorrentes(client):
    _setup_dados(client)

    response = client.get(f"/dashboard/compras-recorrentes?ano_mes={ANO_MES}")
    assert response.status_code == 200
    data = response.get_json()

    assert len(data["mes"]) == 1
    assert data["mes"][0]["descricao"] == "Netflix"
    assert data["mes"][0]["ocorrencias"] == 2
    assert data["mes"][0]["total"] == 100.0

    netflix_geral = next(
        item for item in data["total_geral"] if item["descricao"] == "Netflix"
    )
    assert netflix_geral["ocorrencias"] == 4
    assert netflix_geral["total"] == 200.0


def test_categorias_top(client):
    _setup_dados(client)

    response = client.get(f"/dashboard/categorias-top?ano_mes={ANO_MES}")
    assert response.status_code == 200
    data = response.get_json()

    assert data["mes"][0]["categoria_nome"] == "Alimentação"
    assert data["mes"][0]["total"] == 950.0
    assert data["mes"][0]["qtd"] == 3

    assert data["total_geral"][0]["categoria_nome"] == "Alimentação"
    assert data["total_geral"][0]["total"] == 1050.0


def test_patrimonio_evolucao(client):
    _setup_dados(client)

    response = client.get("/dashboard/patrimonio")
    assert response.status_code == 200
    data = response.get_json()

    assert len(data["serie"]) == 2
    assert data["serie"][0]["ano_mes"] == ANO_MES_ANT
    assert data["serie"][1]["ano_mes"] == ANO_MES
    assert data["serie"][1]["patrimonio_efetivo"] == 620.0


def test_orcamentos_resumo(client):
    _setup_dados(client)

    response = client.get(f"/dashboard/orcamentos-resumo?ano_mes={ANO_MES}")
    assert response.status_code == 200
    data = response.get_json()

    assert data["totais"]["valor_planejado"] == 1300.0
    assert data["totais"]["valor_gasto"] == 1100.0
    assert data["totais"]["saldo_restante"] == 200.0
    assert data["totais"]["percentual_usado"] == 84.62
    assert len(data["por_categoria"]) == 2
