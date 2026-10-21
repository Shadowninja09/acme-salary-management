from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SPA_MARKER = "spa-index-marker"


def _write_frontend_dist(root: Path) -> Path:
    dist = root / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        f"<!doctype html><html><body>{SPA_MARKER}</body></html>\n",
        encoding="utf-8",
    )
    (dist / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8")
    (assets / "app.js").write_text("window.__ACME_ASSET__=1;\n", encoding="utf-8")
    return dist


def test_spa_index_and_unknown_frontend_route_serve_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = _write_frontend_dist(tmp_path)
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    client = TestClient(app)

    index = client.get("/")
    assert index.status_code == 200
    assert SPA_MARKER in index.text
    assert "text/html" in index.headers.get("content-type", "")

    nested = client.get("/employees/41")
    assert nested.status_code == 200
    assert SPA_MARKER in nested.text


def test_existing_static_asset_is_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = _write_frontend_dist(tmp_path)
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    client = TestClient(app)

    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "window.__ACME_ASSET__=1;" in response.text


def test_health_and_missing_api_routes_are_not_spa_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = _write_frontend_dist(tmp_path)
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert SPA_MARKER not in health.text

    missing_api = client.get("/api/v1/does-not-exist")
    assert missing_api.status_code == 404
    assert missing_api.headers.get("content-type", "").startswith("application/json")
    assert SPA_MARKER not in missing_api.text
    assert missing_api.json()["detail"] == "Not Found"

    employees = client.get("/api/v1/employees")
    assert employees.status_code == 401
    assert employees.headers.get("content-type", "").startswith("application/json")
    assert SPA_MARKER not in employees.text
    assert employees.json()["detail"] == "Not authenticated"


def test_missing_frontend_dist_returns_json_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing-dist"))
    client = TestClient(app)

    response = client.get("/employees/41")
    assert response.status_code == 404
    assert response.headers.get("content-type", "").startswith("application/json")
    assert response.json()["detail"] == "Not Found"
