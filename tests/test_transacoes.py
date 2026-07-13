from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.servicos.transacoes import TransacaoNaoEncontradaError


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
    with patch("app.rotas.transacoes.usuario_logado", return_value=usuario):
        with patch("app.rotas.categorias.usuario_logado", return_value=usuario):
            yield usuario


def test_listar_sem_sessao(client):
    response = client.get("/transacoes", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_categorias_sem_sessao(client):
    response = client.get("/categorias")
    assert response.status_code == 401


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_listar_com_sessao(mock_listar, client, usuario_logado):
    response = client.get("/transacoes")
    assert response.status_code == 200
    assert b"Transa" in response.data
    mock_listar.assert_called_once_with(usuario_logado["id"])


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_listar_com_filtros(mock_listar, client, usuario_logado):
    response = client.get(
        "/transacoes?data_inicio=2026-07-01&data_fim=2026-07-31&categoria_id=1&pago=true"
    )
    assert response.status_code == 200
    mock_listar.assert_called_once()
    kwargs = mock_listar.call_args.kwargs
    assert kwargs["data_inicio"].isoformat() == "2026-07-01"
    assert kwargs["data_fim"].isoformat() == "2026-07-31"
    assert kwargs["categoria_id"] == 1
    assert kwargs["pago"] is True


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_listar_filtro_data_invalida(mock_listar, client, usuario_logado):
    response = client.get("/transacoes?data_inicio=2026-13-01")
    assert response.status_code == 200
    mock_listar.assert_called_once_with(usuario_logado["id"])


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_listar_filtro_intervalo_invertido(mock_listar, client, usuario_logado):
    response = client.get(
        "/transacoes?data_inicio=2026-07-31&data_fim=2026-07-01"
    )
    assert response.status_code == 200
    mock_listar.assert_called_once_with(usuario_logado["id"])


@patch("app.rotas.transacoes.categoria_ativa_existe", return_value=False)
@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_listar_filtro_categoria_invalida(mock_listar, mock_categoria, client, usuario_logado):
    response = client.get("/transacoes?categoria_id=99999")
    assert response.status_code == 200
    mock_listar.assert_called_once_with(usuario_logado["id"])


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_listar_json_com_filtros(mock_listar, client, usuario_logado):
    from datetime import date
    from decimal import Decimal

    mock_listar.return_value = [
        {
            "id": 1,
            "data_compra": date(2026, 7, 13),
            "descricao": "Almoço",
            "categoria_id": 1,
            "categoria_nome": "Alimentação",
            "valor": Decimal("45.90"),
            "pago": True,
            "pago_por_terceiro": False,
            "nome_terceiro": None,
            "origem": "manual",
            "criado_em": None,
            "atualizado_em": None,
        }
    ]
    response = client.get(
        "/transacoes?pago=true",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["pago"] is True


@patch("app.rotas.categorias.listar_ativas", return_value=[{"id": 1, "nome": "Alimentação"}])
def test_categorias_com_sessao(mock_listar, client, usuario_logado):
    response = client.get("/categorias")
    assert response.status_code == 200
    data = response.get_json()
    assert data[0]["nome"] == "Alimentação"


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_criar_validacao_descricao(mock_listar, client, usuario_logado):
    response = client.post(
        "/transacoes",
        data={
            "data_compra": "2026-07-13",
            "descricao": "",
            "categoria_id": "1",
            "valor": "10.00",
        },
    )
    assert response.status_code == 200
    assert b"Descri" in response.data


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_criar_validacao_nome_terceiro(mock_listar, client, usuario_logado):
    response = client.post(
        "/transacoes",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Almoço",
            "categoria_id": "1",
            "valor": "45.90",
            "pago_por_terceiro": "true",
        },
    )
    assert response.status_code == 200
    assert b"terceiro" in response.data.lower()


@patch("app.rotas.transacoes.criar_transacao")
@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_criar_sucesso(mock_listar, mock_criar, client, usuario_logado):
    mock_criar.return_value = {"id": 1}
    response = client.post(
        "/transacoes",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Almoço",
            "categoria_id": "1",
            "valor": "45.90",
            "pago": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/transacoes")
    mock_criar.assert_called_once()


@patch("app.rotas.transacoes.atualizar_transacao")
def test_atualizar_nao_encontrada(mock_atualizar, client, usuario_logado):
    mock_atualizar.side_effect = TransacaoNaoEncontradaError("Transação não encontrada.")
    response = client.put(
        "/transacoes/999",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Almoço",
            "categoria_id": "1",
            "valor": "45.90",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/transacoes")


@patch("app.rotas.transacoes.atualizar_transacao")
def test_atualizar_sucesso_json(mock_atualizar, client, usuario_logado):
    mock_atualizar.return_value = {"id": 1}
    response = client.put(
        "/transacoes/1",
        data={
            "data_compra": "2026-07-13",
            "descricao": "Jantar",
            "categoria_id": "1",
            "valor": "60.00",
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert response.get_json()["sucesso"] is True


def test_excluir_sem_sessao(client):
    response = client.delete("/transacoes/1", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


@patch("app.rotas.transacoes.excluir_transacao")
def test_excluir_sucesso_json(mock_excluir, client, usuario_logado):
    response = client.delete(
        "/transacoes/1",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 204
    mock_excluir.assert_called_once_with(usuario_logado["id"], 1)


@patch("app.rotas.transacoes.excluir_transacao")
def test_excluir_nao_encontrada(mock_excluir, client, usuario_logado):
    mock_excluir.side_effect = TransacaoNaoEncontradaError("Transação não encontrada.")
    response = client.delete(
        "/transacoes/999",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 404


def test_importar_sem_sessao(client):
    response = client.post("/transacoes/importar", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_importar_sem_arquivo(mock_listar, client, usuario_logado):
    response = client.post(
        "/transacoes/importar",
        data={},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Selecione um arquivo" in response.data


@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_importar_extensao_invalida(mock_listar, client, usuario_logado):
    from io import BytesIO

    response = client.post(
        "/transacoes/importar",
        data={"arquivo": (BytesIO(b"conteudo"), "planilha.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Formato n" in response.data


@patch("app.rotas.transacoes.importar_transacoes", return_value={"importadas": 3, "erros": []})
@patch("app.rotas.transacoes.listar_por_usuario", return_value=[])
def test_importar_sucesso(mock_listar, mock_importar, client, usuario_logado):
    from io import BytesIO

    response = client.post(
        "/transacoes/importar",
        data={"arquivo": (BytesIO(b"data,descricao,categoria,valor\n"), "planilha.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/transacoes")

    with client.session_transaction() as sess:
        assert sess["ultima_importacao"]["importadas"] == 3

    mock_importar.assert_called_once()
