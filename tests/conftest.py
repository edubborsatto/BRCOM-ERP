import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DATABASE = Path(tempfile.gettempdir()) / f"brcom_test_{os.getpid()}.db"
if TEST_DATABASE.exists():
    TEST_DATABASE.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE}"
os.environ["SESSION_SECRET"] = "test-session-secret-with-more-than-32-characters"
os.environ["COOKIE_SECURE"] = "false"
os.environ["BOOTSTRAP_ADMIN_LOGIN"] = "admin"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Administrador"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "SenhaSeguraTeste123"

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    if TEST_DATABASE.exists():
        TEST_DATABASE.unlink()


@pytest.fixture()
def admin_client(client):
    resposta = client.post(
        "/api/login",
        json={"usuario_login": "admin", "senha": "SenhaSeguraTeste123"},
    )
    assert resposta.status_code == 200
    yield client
    client.post("/api/logout")
