from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture
def usuario_logado(client):
    usuario = {
        "id": str(uuid4()),
        "nome": "João",
        "email": "joao@example.com",
    }
    with patch("app.rotas.consultas.usuario_logado", return_value=usuario):
        with patch("app.rotas.categorias.usuario_logado", return_value=usuario):
            yield usuario


def test_listar_sem_sessao(client):
    response = client.get("/consultas", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_listar_json_sem_sessao(client):
    response = client.get("/consultas", headers={"Accept": "application/json"})
    assert response.status_code == 401


@patch("app.rotas.consultas.consultar_transacoes")
def test_listar_com_sessao(mock_consultar, client, usuario_logado):
    mock_consultar.return_value = {
        "transacoes": [],
        "total": 0,
        "pagina": 1,
        "por_pagina": 25,
        "total_paginas": 0,
    }
    response = client.get("/consultas")
    assert response.status_code == 200
    assert b"Consultas personalizadas" in response.data
    mock_consultar.assert_called_once_with(
        usuario_logado["id"],
        condicoes=[],
        pagina=1,
        por_pagina=25,
    )


@patch("app.rotas.consultas.categoria_ativa_existe", return_value=True)
@patch("app.rotas.consultas.consultar_transacoes")
def test_listar_com_duas_condicoes(mock_consultar, mock_categoria, client, usuario_logado):
    mock_consultar.return_value = {
        "transacoes": [],
        "total": 0,
        "pagina": 1,
        "por_pagina": 25,
        "total_paginas": 0,
    }
    response = client.get(
        "/consultas?f0_campo=valor&f0_operador=maior_que&f0_valor=100"
        "&f1_campo=pago&f1_operador=igual&f1_valor=false"
    )
    assert response.status_code == 200
    mock_consultar.assert_called_once()
    condicoes = mock_consultar.call_args.kwargs["condicoes"]
    assert len(condicoes) == 2
    assert condicoes[0]["campo"] == "valor"
    assert condicoes[0]["operador"] == "maior_que"
    assert condicoes[1]["campo"] == "pago"
    assert condicoes[1]["valor"] is False


@patch("app.rotas.consultas.consultar_transacoes")
def test_listar_campo_invalido_json(mock_consultar, client, usuario_logado):
    response = client.get(
        "/consultas?f0_campo=descricao&f0_operador=igual&f0_valor=teste",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert "Campo inválido" in response.get_json()["erro"]
    mock_consultar.assert_not_called()


@patch("app.rotas.consultas.consultar_transacoes")
def test_listar_operador_invalido_json(mock_consultar, client, usuario_logado):
    response = client.get(
        "/consultas?f0_campo=pago&f0_operador=contem&f0_valor=true",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    mock_consultar.assert_not_called()


@patch("app.rotas.consultas.consultar_transacoes")
def test_listar_entre_sem_valor2_json(mock_consultar, client, usuario_logado):
    response = client.get(
        "/consultas?f0_campo=valor&f0_operador=entre&f0_valor=10",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert "Intervalo" in response.get_json()["erro"]
    mock_consultar.assert_not_called()


@patch("app.rotas.consultas.consultar_transacoes")
def test_listar_max_condicoes_excedido_json(mock_consultar, client, usuario_logado):
    query = "&".join(
        f"f{i}_campo=pago&f{i}_operador=igual&f{i}_valor=true" for i in range(6)
    )
    response = client.get(
        f"/consultas?{query}",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert "Máximo de 5" in response.get_json()["erro"]
    mock_consultar.assert_not_called()


@patch("app.rotas.consultas.consultar_transacoes")
def test_listar_paginacao(mock_consultar, client, usuario_logado):
    mock_consultar.return_value = {
        "transacoes": [],
        "total": 50,
        "pagina": 2,
        "por_pagina": 10,
        "total_paginas": 5,
    }
    response = client.get("/consultas?pagina=2&por_pagina=10")
    assert response.status_code == 200
    mock_consultar.assert_called_once_with(
        usuario_logado["id"],
        condicoes=[],
        pagina=2,
        por_pagina=10,
    )


@patch("app.rotas.consultas.categoria_ativa_existe", return_value=True)
@patch("app.rotas.consultas.consultar_transacoes")
def test_listar_json_com_resultado(mock_consultar, mock_categoria, client, usuario_logado):
    from datetime import date
    from decimal import Decimal

    mock_consultar.return_value = {
        "transacoes": [
            {
                "id": 1,
                "data_compra": date(2026, 7, 13),
                "descricao": "Almoço",
                "categoria_id": 1,
                "categoria_nome": "Alimentação",
                "valor": Decimal("45.90"),
                "pago": False,
                "pago_por_terceiro": False,
                "nome_terceiro": None,
                "origem": "manual",
                "criado_em": None,
                "atualizado_em": None,
            }
        ],
        "total": 1,
        "pagina": 1,
        "por_pagina": 25,
        "total_paginas": 1,
    }
    response = client.get(
        "/consultas?f0_campo=valor&f0_operador=maior_que&f0_valor=40",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["transacoes"]) == 1
    assert data["paginacao"]["total"] == 1
    assert data["condicoes_aplicadas"][0]["campo"] == "valor"
