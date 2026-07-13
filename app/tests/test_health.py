from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@patch("app.rotas.health.check_db", return_value=True)
def test_health_ok(mock_check_db, client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    mock_check_db.assert_called_once()


@patch("app.rotas.health.check_db", side_effect=Exception("connection refused"))
def test_health_db_unreachable(mock_check_db, client):
    response = client.get("/health")
    assert response.status_code == 503
    data = response.get_json()
    assert data["status"] == "degraded"
    assert data["database"] == "unreachable"
    assert "connection refused" in data["error"]
    mock_check_db.assert_called_once()
