from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.servicos.orcamentos import _calcular_percentual


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
    with patch("app.rotas.orcamentos.usuario_logado", return_value=usuario):
        yield usuario


# --- Testes das funções auxiliares do serviço ---


def test_calcular_percentual_normal():
    resultado = _calcular_percentual(Decimal("150"), Decimal("500"))
    assert resultado == Decimal("30.00")


def test_calcular_percentual_zero_gasto():
    resultado = _calcular_percentual(Decimal("0"), Decimal("500"))
    assert resultado == Decimal("0.00")


def test_calcular_percentual_acima_de_cem():
    resultado = _calcular_percentual(Decimal("600"), Decimal("500"))
    assert resultado == Decimal("120.00")


def test_calcular_percentual_planejado_zero():
    resultado = _calcular_percentual(Decimal("100"), Decimal("0"))
    assert resultado is None


# --- Testes das rotas ---


def test_listar_sem_sessao(client):
    response = client.get("/orcamentos", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_status_json_sem_sessao(client):
    response = client.get(
        "/orcamentos/2026-07/status",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401


@patch("app.rotas.orcamentos.status_por_mes", return_value=[])
def test_listar_com_sessao(mock_status, client, usuario_logado):
    response = client.get("/orcamentos?ano_mes=2026-07")
    assert response.status_code == 200
    assert b"Or" in response.data  # "Orçamentos"
    mock_status.assert_called_once_with(usuario_logado["id"], "2026-07")


@patch("app.rotas.orcamentos.status_por_mes")
def test_status_json_com_sessao(mock_status, client, usuario_logado):
    mock_status.return_value = [
        {
            "categoria_id": 1,
            "categoria_nome": "Alimentação",
            "ano_mes": "2026-07",
            "valor_planejado": Decimal("500"),
            "valor_gasto": Decimal("150"),
            "saldo_restante": Decimal("350"),
            "percentual_usado": Decimal("30.00"),
        }
    ]
    response = client.get(
        "/orcamentos/2026-07/status",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["categoria_nome"] == "Alimentação"
    assert data[0]["percentual_usado"] == 30.0
    assert data[0]["saldo_restante"] == 350.0


@patch("app.rotas.orcamentos.status_por_mes", return_value=[])
def test_salvar_validacao_ano_mes_vazio(mock_status, client, usuario_logado):
    response = client.post(
        "/orcamentos",
        data={
            "ano_mes": "",
            "categoria_id": "1",
            "valor_planejado": "500",
        },
    )
    assert response.status_code == 200
    assert b"M" in response.data  # "Mês é obrigatório"


@patch("app.rotas.orcamentos.status_por_mes", return_value=[])
def test_salvar_validacao_ano_mes_invalido(mock_status, client, usuario_logado):
    response = client.post(
        "/orcamentos",
        data={
            "ano_mes": "2026/07",
            "categoria_id": "1",
            "valor_planejado": "500",
        },
    )
    assert response.status_code == 200
    assert b"inv" in response.data.lower()


@patch("app.rotas.orcamentos.salvar_orcamento")
@patch("app.rotas.orcamentos.status_por_mes", return_value=[])
def test_salvar_sucesso(mock_status, mock_salvar, client, usuario_logado):
    mock_salvar.return_value = {"ano_mes": "2026-07"}
    response = client.post(
        "/orcamentos",
        data={
            "ano_mes": "2026-07",
            "categoria_id": "1",
            "valor_planejado": "500",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "ano_mes=2026-07" in response.headers["Location"]
    mock_salvar.assert_called_once()


@patch("app.rotas.orcamentos.status_por_mes", return_value=[])
def test_status_ano_mes_invalido(mock_status, client, usuario_logado):
    response = client.get(
        "/orcamentos/2026-13/status",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
