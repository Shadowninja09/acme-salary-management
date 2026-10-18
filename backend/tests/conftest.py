import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://acme:acme@localhost:5432/acme_test",
)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
