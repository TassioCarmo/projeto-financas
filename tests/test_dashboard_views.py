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


ROTAS_HTML = [
    "/dashboard",
    "/dashboard/categorias",
    "/dashboard/recorrencias",
    "/dashboard/orcamentos",
]


@pytest.mark.parametrize("rota", ROTAS_HTML)
def test_sem_sessao_redirect_login(client, rota):
    response = client.get(rota, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


@pytest.mark.parametrize("rota", ROTAS_HTML)
def test_com_sessao_retorna_200(client, rota, usuario_logado):
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get(rota)
    assert response.status_code == 200
    assert b"canvas" in response.data
    assert b"filtro_ano_mes" in response.data
    assert b"Vis" in response.data or b"Detalhamento" in response.data or b"Ranking" in response.data or b"Status" in response.data


@pytest.mark.parametrize("rota", ROTAS_HTML)
def test_subnav_preserva_ano_mes(client, rota, usuario_logado):
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get(f"{rota}?ano_mes=2026-07")
    assert response.status_code == 200
    assert b"2026-07" in response.data
    assert b"/dashboard/categorias?ano_mes=2026-07" in response.data or b"ano_mes=2026-07" in response.data


@patch("app.rotas.dashboard.usuario_logado")
def test_ano_mes_invalido_html_continua(mock_login, client, usuario_logado):
    mock_login.return_value = usuario_logado
    response = client.get("/dashboard?ano_mes=2026-13")
    assert response.status_code == 200
    assert b"canvas" in response.data


def test_visao_geral_inclui_chart_js(client, usuario_logado):
    with patch("app.rotas.dashboard.usuario_logado", return_value=usuario_logado):
        response = client.get("/dashboard")
    assert b"chart.js" in response.data
    assert b"chart-fluxo" in response.data
    assert b"chart-patrimonio" in response.data
