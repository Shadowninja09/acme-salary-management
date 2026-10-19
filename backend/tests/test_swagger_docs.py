from fastapi.testclient import TestClient

from app.main import inject_swagger_csrf_request_interceptor
from app.services.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


def test_swagger_docs_include_csrf_header_interceptor(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    html = response.text
    assert "requestInterceptor" in html
    assert CSRF_COOKIE_NAME in html
    assert CSRF_HEADER_NAME in html
    assert "document.cookie" in html
    assert 'existing === ""' in html
    assert "console.log" not in html
    assert "console.debug" not in html


def test_swagger_interceptor_is_injected_once() -> None:
    html = "    presets: [\n        SwaggerUIBundle.presets.apis,\n    presets: [\n"
    injected = inject_swagger_csrf_request_interceptor(html)

    assert injected.count("requestInterceptor") == 1
    assert injected.index("requestInterceptor") < injected.index("presets")
