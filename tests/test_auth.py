from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.servicos.auth import encerrar_sessao, iniciar_sessao, usuario_logado
from app.servicos.usuarios import EmailJaCadastradoError, hash_senha, verificar_senha


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


def test_hash_e_verificar_senha():
    senha = "senha123"
    senha_hash = hash_senha(senha)
    assert verificar_senha(senha, senha_hash)
    assert not verificar_senha("outra", senha_hash)


def test_usuario_logado_sem_sessao(app):
    with app.test_request_context():
        encerrar_sessao()
        assert usuario_logado() is None


def test_usuario_logado_com_sessao(app):
    usuario = {
        "id": uuid4(),
        "nome": "Maria",
        "email": "maria@example.com",
    }
    with app.test_request_context():
        iniciar_sessao(usuario)
        logado = usuario_logado()
        assert logado is not None
        assert logado["nome"] == "Maria"
        assert logado["email"] == "maria@example.com"
        assert logado["id"] == str(usuario["id"])


def test_cadastro_get(client):
    response = client.get("/auth/cadastro")
    assert response.status_code == 200
    assert b"Cadastro" in response.data


@patch("app.rotas.auth.criar_usuario")
def test_cadastro_post_sucesso(mock_criar, client):
    mock_criar.return_value = {
        "id": uuid4(),
        "nome": "João",
        "email": "joao@example.com",
    }
    response = client.post(
        "/auth/cadastro",
        data={"nome": "João", "email": "joao@example.com", "senha": "senha123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")
    mock_criar.assert_called_once_with("João", "joao@example.com", "senha123")


@patch("app.rotas.auth.criar_usuario")
def test_cadastro_post_email_duplicado(mock_criar, client):
    mock_criar.side_effect = EmailJaCadastradoError("Email já cadastrado")
    response = client.post(
        "/auth/cadastro",
        data={"nome": "João", "email": "joao@example.com", "senha": "senha123"},
    )
    assert response.status_code == 200
    assert b"Email j" in response.data


def test_cadastro_post_validacao(client):
    response = client.post(
        "/auth/cadastro",
        data={"nome": "", "email": "invalido", "senha": "123"},
    )
    assert response.status_code == 200
    assert b"Nome" in response.data or b"Email" in response.data or b"Senha" in response.data


def test_login_get(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Login" in response.data


@patch("app.rotas.auth.verificar_senha", return_value=True)
@patch("app.rotas.auth.buscar_por_email")
def test_login_post_sucesso(mock_buscar, mock_verificar, client):
    mock_buscar.return_value = {
        "id": uuid4(),
        "nome": "João",
        "email": "joao@example.com",
        "senha_hash": "hash",
    }
    response = client.post(
        "/auth/login",
        data={"email": "joao@example.com", "senha": "senha123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/perfil")


@patch("app.rotas.auth.buscar_por_email", return_value=None)
def test_login_post_credenciais_invalidas(mock_buscar, client):
    response = client.post(
        "/auth/login",
        data={"email": "joao@example.com", "senha": "errada"},
    )
    assert response.status_code == 200
    assert b"Email ou senha incorretos" in response.data


def test_perfil_sem_sessao(client):
    response = client.get("/perfil", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


@patch("app.rotas.auth.verificar_senha", return_value=True)
@patch("app.rotas.auth.buscar_por_email")
def test_perfil_com_sessao(mock_buscar, mock_verificar, client):
    mock_buscar.return_value = {
        "id": uuid4(),
        "nome": "João",
        "email": "joao@example.com",
        "senha_hash": "hash",
    }
    client.post(
        "/auth/login",
        data={"email": "joao@example.com", "senha": "senha123"},
    )
    response = client.get("/perfil")
    assert response.status_code == 200
    assert b"Jo" in response.data
    assert b"joao@example.com" in response.data


@patch("app.rotas.auth.verificar_senha", return_value=True)
@patch("app.rotas.auth.buscar_por_email")
def test_logout(mock_buscar, mock_verificar, client):
    mock_buscar.return_value = {
        "id": uuid4(),
        "nome": "João",
        "email": "joao@example.com",
        "senha_hash": "hash",
    }
    client.post(
        "/auth/login",
        data={"email": "joao@example.com", "senha": "senha123"},
    )
    response = client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    response = client.get("/perfil", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")
