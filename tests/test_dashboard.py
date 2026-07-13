from decimal import Decimal
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
def usuario_logado():
    return {
        "id": str(uuid4()),
        "nome": "João",
        "email": "joao@example.com",
    }


ROTAS_COM_ANO_MES = [
    "/dashboard/fluxo-caixa",
    "/dashboard/compras-recorrentes",
    "/dashboard/categorias-top",
    "/dashboard/orcamentos-resumo",
]

ROTAS_TODAS = ROTAS_COM_ANO_MES + ["/dashboard/patrimonio"]


@pytest.mark.parametrize("rota", ROTAS_TODAS)
def test_sem_sessao_retorna_401(client, rota):
    response = client.get(rota)
    assert response.status_code == 401
    assert response.get_json()["erro"] == "Não autenticado."


@pytest.mark.parametrize("rota", ROTAS_COM_ANO_MES)
def test_ano_mes_invalido_retorna_400(client, rota, usuario_logado):
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get(f"{rota}?ano_mes=2026-13")
    assert response.status_code == 400


@patch("app.rotas.dashboard.fluxo_caixa")
def test_fluxo_caixa_serializa_decimals(mock_fluxo, client, usuario_logado):
    mock_fluxo.return_value = {
        "ano_mes": "2026-07",
        "mes": {
            "entrou": Decimal("5120"),
            "saiu": Decimal("3200"),
            "saldo": Decimal("1920"),
        },
        "total_geral": {
            "entrou": Decimal("45000"),
            "saiu": Decimal("28000"),
            "saldo": Decimal("17000"),
        },
    }
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get("/dashboard/fluxo-caixa?ano_mes=2026-07")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mes"]["entrou"] == 5120.0
    assert data["mes"]["saiu"] == 3200.0
    assert data["total_geral"]["saldo"] == 17000.0


@patch("app.rotas.dashboard.compras_recorrentes")
def test_compras_recorrentes_serializa(mock_compras, client, usuario_logado):
    mock_compras.return_value = {
        "ano_mes": "2026-07",
        "mes": [
            {
                "descricao": "Netflix",
                "categoria_id": 1,
                "categoria_nome": "Lazer",
                "ocorrencias": 2,
                "total": Decimal("99.80"),
                "media": Decimal("49.90"),
            }
        ],
        "total_geral": [],
    }
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get("/dashboard/compras-recorrentes?ano_mes=2026-07")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mes"][0]["total"] == 99.8
    assert data["mes"][0]["ocorrencias"] == 2


@patch("app.rotas.dashboard.categorias_top")
def test_categorias_top_serializa(mock_top, client, usuario_logado):
    mock_top.return_value = {
        "ano_mes": "2026-07",
        "mes": [
            {
                "categoria_id": 1,
                "categoria_nome": "Alimentação",
                "total": Decimal("850"),
                "qtd": 12,
                "percentual": Decimal("65.00"),
            }
        ],
        "total_geral": [],
    }
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get("/dashboard/categorias-top?ano_mes=2026-07")

    assert response.status_code == 200
    data = response.get_json()
    assert data["mes"][0]["categoria_nome"] == "Alimentação"
    assert data["mes"][0]["percentual"] == 65.0


@patch("app.rotas.dashboard.patrimonio_evolucao")
def test_patrimonio_serializa(mock_patrimonio, client, usuario_logado):
    mock_patrimonio.return_value = {
        "serie": [
            {
                "ano_mes": "2026-01",
                "renda": Decimal("5000"),
                "investimento": Decimal("500"),
                "rendimentos": Decimal("100"),
                "patrimonio": None,
                "patrimonio_sugerido": Decimal("600"),
                "patrimonio_efetivo": Decimal("600"),
            }
        ]
    }
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get("/dashboard/patrimonio")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["serie"]) == 1
    assert data["serie"][0]["patrimonio_efetivo"] == 600.0


@patch("app.rotas.dashboard.orcamentos_resumo")
def test_orcamentos_resumo_serializa(mock_resumo, client, usuario_logado):
    mock_resumo.return_value = {
        "ano_mes": "2026-07",
        "totais": {
            "valor_planejado": Decimal("3000"),
            "valor_gasto": Decimal("2450"),
            "saldo_restante": Decimal("550"),
            "percentual_usado": Decimal("81.67"),
        },
        "por_categoria": [
            {
                "categoria_id": 1,
                "categoria_nome": "Alimentação",
                "ano_mes": "2026-07",
                "valor_planejado": Decimal("3000"),
                "valor_gasto": Decimal("2450"),
                "saldo_restante": Decimal("550"),
                "percentual_usado": Decimal("81.67"),
            }
        ],
    }
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get("/dashboard/orcamentos-resumo?ano_mes=2026-07")

    assert response.status_code == 200
    data = response.get_json()
    assert data["totais"]["percentual_usado"] == 81.67
    assert len(data["por_categoria"]) == 1
