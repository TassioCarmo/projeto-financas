from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.servicos.resumo_mensal import (
    _calcular_patrimonio_sugerido,
    _mes_anterior,
)


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
    with patch("app.rotas.resumo_mensal.usuario_logado", return_value=usuario):
        yield usuario


# --- Testes das funções auxiliares do serviço ---


def test_mes_anterior_marco():
    assert _mes_anterior("2026-03") == "2026-02"


def test_mes_anterior_janeiro():
    assert _mes_anterior("2026-01") is None


@patch("app.servicos.resumo_mensal._buscar_por_mes", return_value=None)
def test_calcular_patrimonio_sugerido_sem_mes_anterior(mock_buscar):
    usuario_id = str(uuid4())
    resultado = _calcular_patrimonio_sugerido(
        usuario_id, "2026-01", Decimal("1000"), Decimal("50")
    )
    assert resultado == Decimal("1050")
    mock_buscar.assert_not_called()


@patch("app.servicos.resumo_mensal._buscar_por_mes")
def test_calcular_patrimonio_sugerido_com_sugerido_anterior(mock_buscar):
    mock_buscar.return_value = {
        "patrimonio": None,
        "patrimonio_sugerido": Decimal("5000"),
    }
    usuario_id = str(uuid4())
    resultado = _calcular_patrimonio_sugerido(
        usuario_id, "2026-02", Decimal("1000"), Decimal("200")
    )
    assert resultado == Decimal("6200")
    mock_buscar.assert_called_once_with(usuario_id, "2026-01")


@patch("app.servicos.resumo_mensal._buscar_por_mes")
def test_calcular_patrimonio_sugerido_prioriza_patrimonio_manual(mock_buscar):
    mock_buscar.return_value = {
        "patrimonio": Decimal("8000"),
        "patrimonio_sugerido": Decimal("5000"),
    }
    usuario_id = str(uuid4())
    resultado = _calcular_patrimonio_sugerido(
        usuario_id, "2026-02", Decimal("500"), Decimal("100")
    )
    assert resultado == Decimal("8600")


# --- Testes das rotas ---


def test_listar_sem_sessao(client):
    response = client.get("/resumo-mensal", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_listar_json_sem_sessao(client):
    response = client.get(
        "/resumo-mensal",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401


@patch("app.rotas.resumo_mensal.listar_por_ano", return_value=[])
def test_listar_com_sessao(mock_listar, client, usuario_logado):
    response = client.get("/resumo-mensal?ano=2026")
    assert response.status_code == 200
    assert b"Resumo mensal" in response.data
    mock_listar.assert_called_once_with(usuario_logado["id"], 2026)


@patch("app.rotas.resumo_mensal.listar_por_ano", return_value=[])
def test_listar_json_com_sessao(mock_listar, client, usuario_logado):
    mock_listar.return_value = [
        {
            "id": 1,
            "ano_mes": "2026-01",
            "renda": Decimal("5000"),
            "investimento": Decimal("1000"),
            "rendimentos": Decimal("100"),
            "patrimonio": None,
            "patrimonio_sugerido": Decimal("1100"),
            "criado_em": None,
            "atualizado_em": None,
        }
    ]
    response = client.get(
        "/resumo-mensal?ano=2026",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["ano_mes"] == "2026-01"
    assert data[0]["patrimonio_sugerido"] == 1100.0


@patch("app.rotas.resumo_mensal.listar_por_ano", return_value=[])
def test_salvar_validacao_ano_mes_vazio(mock_listar, client, usuario_logado):
    response = client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "",
            "renda": "5000",
            "investimento": "1000",
            "rendimentos": "100",
        },
    )
    assert response.status_code == 200
    assert b"M" in response.data  # "Mês é obrigatório"


@patch("app.rotas.resumo_mensal.listar_por_ano", return_value=[])
def test_salvar_validacao_ano_mes_invalido(mock_listar, client, usuario_logado):
    response = client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026/07",
            "renda": "5000",
            "investimento": "1000",
            "rendimentos": "100",
        },
    )
    assert response.status_code == 200
    assert b"inv" in response.data.lower()


@patch("app.rotas.resumo_mensal.salvar_resumo")
@patch("app.rotas.resumo_mensal.listar_por_ano", return_value=[])
def test_salvar_sucesso(mock_listar, mock_salvar, client, usuario_logado):
    mock_salvar.return_value = {"ano_mes": "2026-07"}
    response = client.post(
        "/resumo-mensal",
        data={
            "ano_mes": "2026-07",
            "renda": "5000",
            "investimento": "1000",
            "rendimentos": "100",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "ano=2026" in response.headers["Location"]
    mock_salvar.assert_called_once()
