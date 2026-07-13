import pytest

from app import create_app
from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations


pytestmark = pytest.mark.integration

EMAIL_A = "resumo-a@example.com"
EMAIL_B = "resumo-b@example.com"
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


def _contar_resumos(email):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM resumo_mensal r
                JOIN usuarios u ON u.id = r.usuario_id
                WHERE u.email = %s
                """,
                (email,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _obter_resumo(email, ano_mes):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.renda, r.investimento, r.rendimentos,
                       r.patrimonio, r.patrimonio_sugerido
                FROM resumo_mensal r
                JOIN usuarios u ON u.id = r.usuario_id
                WHERE u.email = %s AND r.ano_mes = %s
                """,
                (email, ano_mes),
            )
            return cur.fetchone()
    finally:
        conn.close()


def test_fluxo_completo_resumo_mensal(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)

    # 1. Salvar janeiro/2026
    response = client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-01",
            "renda": "5000",
            "investimento": "1000",
            "rendimentos": "100",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"2026-01" in response.data

    # patrimonio_sugerido = 0 + 1000 + 100 = 1100 (janeiro não tem mês anterior)
    row = _obter_resumo(EMAIL_A, "2026-01")
    assert float(row[4]) == 1100.0

    # 2. Upsert: reenviar mesmo mês com valores diferentes
    response = client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-01",
            "renda": "5500",
            "investimento": "1200",
            "rendimentos": "150",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert _contar_resumos(EMAIL_A) == 1

    row = _obter_resumo(EMAIL_A, "2026-01")
    assert float(row[0]) == 5500.0
    assert float(row[4]) == 1350.0  # 0 + 1200 + 150

    # 3. Salvar fevereiro — usa patrimonio_sugerido de janeiro como base
    response = client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-02",
            "renda": "5000",
            "investimento": "500",
            "rendimentos": "50",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    row_fev = _obter_resumo(EMAIL_A, "2026-02")
    assert float(row_fev[4]) == 1900.0  # 1350 + 500 + 50

    # 4. GET JSON com ambos os meses
    response = client.get(
        "/resumo-mensal?ano=2026",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    assert data[0]["ano_mes"] == "2026-01"
    assert data[1]["ano_mes"] == "2026-02"


def test_patrimonio_manual_priorizado_na_base(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)

    # Janeiro com patrimonio manual
    client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-01",
            "renda": "5000",
            "investimento": "1000",
            "rendimentos": "100",
            "patrimonio": "10000",
        },
        follow_redirects=True,
    )

    # Fevereiro — base deve ser 10000 (manual), não 1100 (sugerido)
    client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-02",
            "renda": "5000",
            "investimento": "500",
            "rendimentos": "50",
        },
        follow_redirects=True,
    )

    row = _obter_resumo(EMAIL_A, "2026-02")
    assert float(row[4]) == 10550.0  # 10000 + 500 + 50


def test_patrimonio_manual_nao_sobrescrito_no_update(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)

    # Salvar com patrimonio manual
    client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-03",
            "renda": "5000",
            "investimento": "1000",
            "rendimentos": "100",
            "patrimonio": "8000",
        },
        follow_redirects=True,
    )

    # Atualizar sem enviar patrimonio — deve manter 8000
    client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-03",
            "renda": "6000",
            "investimento": "2000",
            "rendimentos": "200",
        },
        follow_redirects=True,
    )

    row = _obter_resumo(EMAIL_A, "2026-03")
    assert float(row[3]) == 8000.0  # patrimonio manual mantido


def test_isolamento_entre_usuarios(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-06",
            "renda": "5000",
            "investimento": "1000",
            "rendimentos": "100",
        },
        follow_redirects=True,
    )

    client.post("/auth/logout", follow_redirects=True)
    _cadastrar_e_logar(client, NOME_B, EMAIL_B)

    response = client.get("/resumo-mensal?ano=2026")
    assert response.status_code == 200
    assert b"2026-06" not in response.data
    assert b"Nenhum m" in response.data

    assert _contar_resumos(EMAIL_B) == 0
    assert _contar_resumos(EMAIL_A) == 1
