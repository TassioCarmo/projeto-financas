import pytest

from app import create_app
from app.servicos.db import get_connection
from app.servicos.migrations import run_migrations


pytestmark = pytest.mark.integration

EMAIL_A = "consultas-a@example.com"
EMAIL_B = "consultas-b@example.com"
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


def test_consulta_combinada_valor_e_pago(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_id()

    _cadastrar_transacao(client, "2026-07-10", "Gasto alto nao pago", categoria_id, "150.00", pago=False)
    _cadastrar_transacao(client, "2026-07-11", "Gasto alto pago", categoria_id, "200.00", pago=True)
    _cadastrar_transacao(client, "2026-07-12", "Gasto baixo nao pago", categoria_id, "50.00", pago=False)

    response = client.get(
        "/consultas?f0_campo=valor&f0_operador=maior_que&f0_valor=100"
        "&f1_campo=pago&f1_operador=igual&f1_valor=false"
    )
    assert response.status_code == 200
    assert b"Gasto alto nao pago" in response.data
    assert b"Gasto alto pago" not in response.data
    assert b"Gasto baixo nao pago" not in response.data

    response = client.get(
        "/consultas?f0_campo=valor&f0_operador=maior_que&f0_valor=100"
        "&f1_campo=pago&f1_operador=igual&f1_valor=false",
        headers={"Accept": "application/json"},
    )
    data = response.get_json()
    assert data["paginacao"]["total"] == 1
    assert data["transacoes"][0]["descricao"] == "Gasto alto nao pago"


def test_isolamento_entre_usuarios_consultas(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_id()
    _cadastrar_transacao(client, "2026-07-10", "Gasto secreto A", categoria_id, "300.00", pago=False)

    client.post("/auth/logout", follow_redirects=True)
    _cadastrar_e_logar(client, NOME_B, EMAIL_B)

    response = client.get(
        "/consultas?f0_campo=valor&f0_operador=maior_que&f0_valor=100"
        "&f1_campo=pago&f1_operador=igual&f1_valor=false"
    )
    assert response.status_code == 200
    assert b"Gasto secreto A" not in response.data


def test_sql_injection_nao_vaza_dados(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_id()
    _cadastrar_transacao(client, "2026-07-10", "Transacao legitima", categoria_id, "80.00")

    client.post("/auth/logout", follow_redirects=True)
    _cadastrar_e_logar(client, NOME_B, EMAIL_B)

    response = client.get(
        "/consultas?f0_campo=valor&f0_operador=igual&f0_valor='; DROP TABLE transacoes; --",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.get_json()["erro"] == "Valor inválido."


def test_paginacao_consultas(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)
    categoria_id = _obter_categoria_id()

    for i in range(1, 8):
        _cadastrar_transacao(
            client,
            f"2026-07-{i:02d}",
            f"Transacao {i}",
            categoria_id,
            f"{10 + i}.00",
        )

    response = client.get(
        "/consultas?por_pagina=3&pagina=1",
        headers={"Accept": "application/json"},
    )
    pagina1 = response.get_json()
    assert pagina1["paginacao"]["total"] == 7
    assert pagina1["paginacao"]["total_paginas"] == 3
    assert len(pagina1["transacoes"]) == 3

    response = client.get(
        "/consultas?por_pagina=3&pagina=2",
        headers={"Accept": "application/json"},
    )
    pagina2 = response.get_json()
    assert len(pagina2["transacoes"]) == 3

    ids_pagina1 = {t["id"] for t in pagina1["transacoes"]}
    ids_pagina2 = {t["id"] for t in pagina2["transacoes"]}
    assert ids_pagina1.isdisjoint(ids_pagina2)


def test_consulta_categoria_contem(client):
    _cadastrar_e_logar(client, NOME_A, EMAIL_A)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categorias WHERE nome = %s AND ativa = TRUE",
                ("Alimentação",),
            )
            cat_alimentacao = cur.fetchone()[0]
            cur.execute(
                "SELECT id FROM categorias WHERE nome = %s AND ativa = TRUE",
                ("Transporte",),
            )
            cat_transporte = cur.fetchone()[0]
    finally:
        conn.close()

    _cadastrar_transacao(client, "2026-07-10", "Mercado", cat_alimentacao, "90.00")
    _cadastrar_transacao(client, "2026-07-11", "Uber", cat_transporte, "25.00")

    response = client.get(
        "/consultas?f0_campo=categoria&f0_operador=contem&f0_valor=Alimen",
        headers={"Accept": "application/json"},
    )
    data = response.get_json()
    assert data["paginacao"]["total"] == 1
    assert data["transacoes"][0]["descricao"] == "Mercado"
