import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CSRF_FAILURE_DETAIL
from app.core.config import Settings, get_settings
from app.main import app
from app.models.employee import Employee
from starlette.requests import Request

from app.services.csrf import (
    CSRF_COOKIE_NAME,
    canonicalize_origin,
    csrf_token_is_valid,
    extract_request_origin,
    issue_csrf_token,
    login_origin_is_trusted,
    submitted_csrf_is_valid,
)
from app.services.sessions import SESSION_COOKIE_NAME, issue_hr_manager_session

_UNIT_SECRET = "test-only-csrf-unit-secret-value!!"
_OTHER_SECRET = "other-test-csrf-unit-secret-value"
_PLACEHOLDER_DATABASE_URL = "postgresql+psycopg://pytest:pytest@127.0.0.1:1/acme_unused"
_TEST_PASSWORD_HASH = PasswordHasher().hash("test-only-unused-password")
EMPLOYEE_PAYLOAD = {
    "employee_code": "EMP-CSRF-001",
    "full_name": "Ada Lovelace",
    "country": "United Kingdom",
    "department": "Engineering",
    "job_title": "Analyst",
    "employment_status": "ACTIVE",
}


class _IsolatedSettings(Settings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[Settings],
        init_settings: object,
        env_settings: object,
        dotenv_settings: object,
        file_secret_settings: object,
    ) -> tuple[object, ...]:
        return (init_settings,)


def _csrf_secret() -> str:
    return get_settings().csrf_signing_secret.get_secret_value()


def _employee_count(db_session: Session) -> int:
    return int(db_session.scalar(select(func.count()).select_from(Employee)) or 0)


def _issue_session(db_session: Session):
    return issue_hr_manager_session(db_session, lifetime_seconds=3600)


def test_csrf_token_generation_and_validation_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.csrf.secrets.token_hex", lambda nbytes: "ab" * nbytes)
    token = issue_csrf_token(session_id=42, secret=_UNIT_SECRET)

    assert token == (
        "v1.42.abababababababababababababababab."
        + token.rsplit(".", 1)[1]
    )
    assert csrf_token_is_valid(token=token, session_id=42, secret=_UNIT_SECRET)
    assert submitted_csrf_is_valid(
        cookie=token,
        header=token,
        session_id=42,
        secret=_UNIT_SECRET,
    )


def test_csrf_rejects_malformed_and_invalid_signatures() -> None:
    token = issue_csrf_token(session_id=7, secret=_UNIT_SECRET)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")

    assert csrf_token_is_valid(token=token, session_id=7, secret=_UNIT_SECRET) is True
    assert csrf_token_is_valid(token="not-a-token", session_id=7, secret=_UNIT_SECRET) is False
    assert csrf_token_is_valid(token="v1.7.nonce", session_id=7, secret=_UNIT_SECRET) is False
    assert csrf_token_is_valid(token=tampered, session_id=7, secret=_UNIT_SECRET) is False
    assert csrf_token_is_valid(token=token, session_id=7, secret=_OTHER_SECRET) is False


def test_csrf_token_is_bound_to_session() -> None:
    token = issue_csrf_token(session_id=11, secret=_UNIT_SECRET)

    assert csrf_token_is_valid(token=token, session_id=11, secret=_UNIT_SECRET) is True
    assert csrf_token_is_valid(token=token, session_id=12, secret=_UNIT_SECRET) is False
    assert submitted_csrf_is_valid(
        cookie=token,
        header=token,
        session_id=12,
        secret=_UNIT_SECRET,
    ) is False


def test_csrf_requires_cookie_and_matching_header() -> None:
    token = issue_csrf_token(session_id=3, secret=_UNIT_SECRET)
    other = issue_csrf_token(session_id=3, secret=_UNIT_SECRET)

    assert submitted_csrf_is_valid(
        cookie=None,
        header=token,
        session_id=3,
        secret=_UNIT_SECRET,
    ) is False
    assert submitted_csrf_is_valid(
        cookie=token,
        header=None,
        session_id=3,
        secret=_UNIT_SECRET,
    ) is False
    assert submitted_csrf_is_valid(
        cookie=token,
        header=other,
        session_id=3,
        secret=_UNIT_SECRET,
    ) is False


def _valid_token_parts() -> tuple[str, str, str, str]:
    token = issue_csrf_token(session_id=7, secret=_UNIT_SECRET)
    version, session_id, nonce, mac = token.split(".")
    return version, session_id, nonce, mac


def test_csrf_rejects_empty_and_malformed_token_components() -> None:
    version, session_id, nonce, mac = _valid_token_parts()

    assert csrf_token_is_valid(token="", session_id=7, secret=_UNIT_SECRET) is False
    assert csrf_token_is_valid(token="...", session_id=7, secret=_UNIT_SECRET) is False
    assert csrf_token_is_valid(
        token=f".{session_id}.{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"{version}..{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"{version}.{session_id}..{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"{version}.{session_id}.{nonce}.",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"{version}.{session_id}.{nonce}.{mac}.extra",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False


def test_csrf_rejects_invalid_version_session_id_nonce_and_mac_formats() -> None:
    _version, session_id, nonce, mac = _valid_token_parts()

    assert csrf_token_is_valid(
        token=f"v2.{session_id}.{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"V1.{session_id}.{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.07.{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.0.{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.-7.{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.+7.{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.7a.{nonce}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.{session_id}.{nonce.upper()}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.{session_id}.{nonce[:31]}.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.{session_id}.{nonce}ff.{mac}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.{session_id}.{nonce}.{mac.upper()}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.{session_id}.{nonce}.{mac[:63]}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.{session_id}.{nonce}.{mac}aa",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False
    assert csrf_token_is_valid(
        token=f"v1.{session_id}.{nonce}.{'g' * 64}",
        session_id=7,
        secret=_UNIT_SECRET,
    ) is False


def test_csrf_accepts_valid_token_and_rejects_wrong_session() -> None:
    token = issue_csrf_token(session_id=11, secret=_UNIT_SECRET)

    assert csrf_token_is_valid(token=token, session_id=11, secret=_UNIT_SECRET) is True
    assert csrf_token_is_valid(token=token, session_id=12, secret=_UNIT_SECRET) is False


def _request(*, origin: str | None = None, referer: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin.encode("utf-8")))
    if referer is not None:
        headers.append((b"referer", referer.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 123),
            "server": ("testserver", 443),
        }
    )


_TRUSTED_ORIGINS = ["https://hr.test"]


def test_origin_hostname_case_and_default_port_are_normalized() -> None:
    trusted = ["https://hr.test", "http://hr.test"]

    assert login_origin_is_trusted(
        _request(origin="https://HR.TEST"),
        trusted,
    )
    assert login_origin_is_trusted(
        _request(origin="https://hr.test:443"),
        trusted,
    )
    assert login_origin_is_trusted(
        _request(origin="https://hr.test:443/"),
        trusted,
    )
    assert login_origin_is_trusted(
        _request(origin="http://hr.test:80"),
        trusted,
    )
    assert extract_request_origin(_request(origin="https://HR.TEST:443")) == (
        "https://hr.test"
    )
    assert extract_request_origin(
        _request(origin=None, referer="https://HR.TEST:443/login")
    ) == "https://hr.test"


def test_origin_rejects_invalid_ports_credentials_null_and_extra_components() -> None:
    assert extract_request_origin(_request(origin="null")) is None
    assert extract_request_origin(_request(origin="https://user:pass@hr.test")) is None
    assert extract_request_origin(_request(origin="https://hr.test:0")) is None
    assert extract_request_origin(_request(origin="https://hr.test:65536")) is None
    assert extract_request_origin(_request(origin="https://hr.test:0443")) is None
    assert extract_request_origin(_request(origin="https://hr.test:abc")) is None
    assert extract_request_origin(_request(origin="https://hr.test/path")) is None
    assert extract_request_origin(_request(origin="https://hr.test/?q=1")) is None
    assert extract_request_origin(_request(origin="https://hr.test/#frag")) is None
    assert extract_request_origin(_request(origin="https://*.test")) is None
    assert login_origin_is_trusted(
        _request(origin="https://hr.test:0"),
        _TRUSTED_ORIGINS,
    ) is False


def test_single_trailing_dns_dot_is_normalized_but_multiple_dots_are_rejected() -> None:
    trusted = ["https://example.com"]

    assert extract_request_origin(_request(origin="https://example.com.")) == (
        "https://example.com"
    )
    assert login_origin_is_trusted(
        _request(origin="https://example.com."),
        trusted,
    )
    assert extract_request_origin(_request(origin="https://example.com..")) is None
    assert extract_request_origin(_request(origin="https://example.com...")) is None
    assert login_origin_is_trusted(
        _request(origin="https://example.com.."),
        trusted,
    ) is False


def test_empty_and_leading_zero_port_specifiers_are_rejected() -> None:
    assert extract_request_origin(_request(origin="https://hr.test:")) is None
    assert extract_request_origin(_request(origin="https://hr.test:080")) is None
    assert extract_request_origin(_request(origin="https://hr.test:0443")) is None
    assert extract_request_origin(_request(origin="http://hr.test:080")) is None
    assert extract_request_origin(_request(origin="https://[::1]:")) is None
    assert extract_request_origin(_request(origin="https://[::1]:0443")) is None
    assert canonicalize_origin("https://hr.test:", allow_path=False) is None


def test_malformed_ipv6_and_extra_authority_delimiters_are_rejected() -> None:
    malformed = (
        "https://[::1",
        "https://::1]",
        "https://[::1]evil",
        "https://[::1]:443extra",
        "https://hr.test:443:80",
        "https://[::1]:443:80",
        "https://hr.test@evil.example",
        "https://hr.test:443@evil.example",
        "https://[::1]@hr.test",
    )
    for value in malformed:
        assert canonicalize_origin(value, allow_path=False) is None
        assert canonicalize_origin(value, allow_path=True) is None
        assert extract_request_origin(_request(origin=value)) is None


def test_ipv4_and_ipv6_origins_normalize_default_ports() -> None:
    assert extract_request_origin(_request(origin="https://127.0.0.1")) == (
        "https://127.0.0.1"
    )
    assert extract_request_origin(_request(origin="https://127.0.0.1:443")) == (
        "https://127.0.0.1"
    )
    assert extract_request_origin(_request(origin="http://127.0.0.1:80")) == (
        "http://127.0.0.1"
    )
    assert extract_request_origin(_request(origin="https://127.0.0.1:8443")) == (
        "https://127.0.0.1:8443"
    )
    assert extract_request_origin(_request(origin="https://[::1]")) == "https://[::1]"
    assert extract_request_origin(_request(origin="https://[::1]:443")) == "https://[::1]"
    assert extract_request_origin(_request(origin="http://[::1]:80")) == "http://[::1]"
    assert extract_request_origin(_request(origin="https://[::1]:4443")) == (
        "https://[::1]:4443"
    )
    assert login_origin_is_trusted(
        _request(origin="https://[::1]:443"),
        ["https://[::1]"],
    )


def test_referer_fragments_are_ignored_when_extracting_origin() -> None:
    # Referer may include a fragment (and query); only the origin is trusted.
    # Origin headers with a fragment remain invalid.
    assert extract_request_origin(
        _request(origin=None, referer="https://hr.test/login#section")
    ) == "https://hr.test"
    assert extract_request_origin(
        _request(origin=None, referer="https://hr.test/login?next=/home#section")
    ) == "https://hr.test"
    assert login_origin_is_trusted(
        _request(origin=None, referer="https://hr.test/app#/employees"),
        _TRUSTED_ORIGINS,
    )
    assert extract_request_origin(_request(origin="https://hr.test/#section")) is None


def test_referer_rejects_malformed_values_and_extracts_origin_from_path() -> None:
    assert extract_request_origin(
        _request(origin=None, referer="https://hr.test/login")
    ) == "https://hr.test"
    assert extract_request_origin(
        _request(origin=None, referer="https://hr.test/login?next=/home")
    ) == "https://hr.test"
    assert extract_request_origin(_request(origin=None, referer="not-a-url")) is None
    assert extract_request_origin(_request(origin=None, referer="://hr.test")) is None
    assert extract_request_origin(_request(origin=None, referer="https://")) is None
    assert extract_request_origin(
        _request(origin=None, referer="javascript:alert(1)")
    ) is None
    assert extract_request_origin(
        _request(origin=None, referer="https://hr.test:65536/login")
    ) is None


def test_untrusted_and_missing_origin_and_referer_are_rejected() -> None:
    assert login_origin_is_trusted(_request(), _TRUSTED_ORIGINS) is False
    assert login_origin_is_trusted(
        _request(origin="https://evil.example"),
        _TRUSTED_ORIGINS,
    ) is False
    assert login_origin_is_trusted(
        _request(origin=None, referer="https://evil.example/login"),
        _TRUSTED_ORIGINS,
    ) is False
    assert login_origin_is_trusted(
        _request(origin="https://hr.test.evil.example"),
        _TRUSTED_ORIGINS,
    ) is False
    assert login_origin_is_trusted(
        _request(origin="https://hr.test:4443"),
        _TRUSTED_ORIGINS,
    ) is False


def test_invalid_origin_is_not_rescued_by_trusted_referer() -> None:
    headers = dict(
        origin="https://evil.example/path",
        referer="https://hr.test/login",
    )
    request = _request(**headers)

    assert extract_request_origin(request) is None
    assert login_origin_is_trusted(request, _TRUSTED_ORIGINS) is False
    assert login_origin_is_trusted(
        _request(origin="null", referer="https://hr.test/login"),
        _TRUSTED_ORIGINS,
    ) is False
    assert login_origin_is_trusted(
        _request(origin="https://user:pass@hr.test", referer="https://hr.test/login"),
        _TRUSTED_ORIGINS,
    ) is False


def test_csrf_signing_secret_is_required() -> None:
    try:
        _IsolatedSettings(
            database_url=_PLACEHOLDER_DATABASE_URL,
            hr_manager_identity="audit-hr-manager",
            hr_manager_username="hr.manager",
            hr_manager_password_hash=_TEST_PASSWORD_HASH,
            session_cookie_secure=False,
            csrf_trusted_origins=["https://hr.test"],
        )
    except ValidationError as exc:
        assert "csrf_signing_secret" in str(exc)
    else:
        raise AssertionError("expected Settings validation to fail")


def test_short_csrf_signing_secret_is_rejected() -> None:
    try:
        _IsolatedSettings(
            database_url=_PLACEHOLDER_DATABASE_URL,
            hr_manager_identity="audit-hr-manager",
            hr_manager_username="hr.manager",
            hr_manager_password_hash=_TEST_PASSWORD_HASH,
            session_cookie_secure=False,
            csrf_signing_secret="too-short",
            csrf_trusted_origins=["https://hr.test"],
        )
    except ValidationError as exc:
        assert "csrf_signing_secret" in str(exc)
    else:
        raise AssertionError("expected Settings validation to fail")


def _origin_settings(origins: list[str]) -> Settings:
    return _IsolatedSettings(
        database_url=_PLACEHOLDER_DATABASE_URL,
        hr_manager_identity="audit-hr-manager",
        hr_manager_username="hr.manager",
        hr_manager_password_hash=_TEST_PASSWORD_HASH,
        session_cookie_secure=False,
        csrf_signing_secret=_UNIT_SECRET,
        csrf_trusted_origins=origins,
    )


def test_wildcard_trusted_origin_is_rejected() -> None:
    try:
        _origin_settings(["https://*.example"])
    except ValidationError as exc:
        assert "csrf_trusted_origins" in str(exc)
    else:
        raise AssertionError("expected Settings validation to fail")


def test_csrf_trusted_origins_accept_valid_hosts_including_ip_literals() -> None:
    settings = _origin_settings(
        [
            "https://hr.test",
            "http://localhost:5173",
            "https://127.0.0.1",
            "https://[::1]",
            "https://[::1]:4443",
        ]
    )
    assert settings.csrf_trusted_origins == [
        "https://hr.test",
        "http://localhost:5173",
        "https://127.0.0.1",
        "https://[::1]",
        "https://[::1]:4443",
    ]


def test_csrf_trusted_origins_keep_default_ports_for_runtime_normalization() -> None:
    settings = _origin_settings(["https://hr.test:443", "http://hr.test:80"])
    assert settings.csrf_trusted_origins == [
        "https://hr.test:443",
        "http://hr.test:80",
    ]


def test_csrf_trusted_origins_reject_malformed_hosts_and_ports() -> None:
    invalid = (
        ["https://"],
        ["https://-hr.test"],
        ["https://hr.test:"],
        ["https://hr.test:0"],
        ["https://hr.test:65536"],
        ["https://hr.test:0443"],
        ["https://hr.test:abc"],
        ["https://[::1"],
        ["https://127.0.0.1:0443"],
        ["https://hr.test/path"],
    )
    for origins in invalid:
        try:
            _origin_settings(list(origins))
        except ValidationError as exc:
            assert "csrf_trusted_origins" in str(exc)
        else:
            raise AssertionError(f"expected Settings validation to fail for {origins}")


def _post_employee(
    client: TestClient,
    raw_token: str,
    csrf_cookie: str | None,
    csrf_header: str | None,
):
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    if csrf_cookie is not None:
        client.cookies.set(CSRF_COOKIE_NAME, csrf_cookie)
    headers = {}
    if csrf_header is not None:
        headers["X-CSRF-Token"] = csrf_header
    try:
        return client.post("/api/v1/employees", json=EMPLOYEE_PAYLOAD, headers=headers)
    finally:
        client.cookies.delete(SESSION_COOKIE_NAME)
        client.cookies.delete(CSRF_COOKIE_NAME)


def test_missing_csrf_cookie_on_employee_create_returns_403(
    api_client: TestClient,
    db_session: Session,
) -> None:
    raw_token, record = _issue_session(db_session)
    token = issue_csrf_token(session_id=record.id, secret=_csrf_secret())

    response = _post_employee(api_client, raw_token, None, token)

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert _employee_count(db_session) == 0


def test_missing_csrf_header_on_employee_create_returns_403(
    api_client: TestClient,
    db_session: Session,
) -> None:
    raw_token, record = _issue_session(db_session)
    token = issue_csrf_token(session_id=record.id, secret=_csrf_secret())

    response = _post_employee(api_client, raw_token, token, None)

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert _employee_count(db_session) == 0


def test_csrf_cookie_header_mismatch_on_employee_create_returns_403(
    api_client: TestClient,
    db_session: Session,
) -> None:
    raw_token, record = _issue_session(db_session)
    cookie = issue_csrf_token(session_id=record.id, secret=_csrf_secret())
    header = issue_csrf_token(session_id=record.id, secret=_csrf_secret())

    response = _post_employee(api_client, raw_token, cookie, header)

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert _employee_count(db_session) == 0


def test_malformed_csrf_token_on_employee_create_returns_403(
    api_client: TestClient,
    db_session: Session,
) -> None:
    raw_token, _record = _issue_session(db_session)
    malformed = "v1.not-valid"

    response = _post_employee(api_client, raw_token, malformed, malformed)

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert _employee_count(db_session) == 0


def test_invalid_csrf_signature_on_employee_create_returns_403(
    api_client: TestClient,
    db_session: Session,
) -> None:
    raw_token, record = _issue_session(db_session)
    token = issue_csrf_token(session_id=record.id, secret=_csrf_secret())
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")

    response = _post_employee(api_client, raw_token, tampered, tampered)

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert _employee_count(db_session) == 0


def test_csrf_token_from_another_session_is_rejected(
    api_client: TestClient,
    db_session: Session,
) -> None:
    raw_token, current = _issue_session(db_session)
    _other_token, other = _issue_session(db_session)
    other_csrf = issue_csrf_token(session_id=other.id, secret=_csrf_secret())

    response = _post_employee(api_client, raw_token, other_csrf, other_csrf)

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert _employee_count(db_session) == 0
    assert current.token_hash not in response.text
    assert other.token_hash not in response.text


def test_valid_session_and_csrf_can_create_employee(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    response = authenticated_client.post("/api/v1/employees", json=EMPLOYEE_PAYLOAD)

    assert response.status_code == 201
    assert response.json()["employee_code"] == "EMP-CSRF-001"
    assert _employee_count(db_session) == 1
    assert CSRF_COOKIE_NAME not in str(response.json()).lower()
    assert SESSION_COOKIE_NAME not in str(response.json()).lower()


def test_employee_get_requires_auth_but_not_csrf_header(
    api_client: TestClient,
    db_session: Session,
) -> None:
    unauthenticated = api_client.get("/api/v1/employees")
    assert unauthenticated.status_code == 401

    raw_token, _record = _issue_session(db_session)
    api_client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    try:
        listed = api_client.get("/api/v1/employees")
        missing = api_client.get("/api/v1/employees/1")
    finally:
        api_client.cookies.delete(SESSION_COOKIE_NAME)

    assert listed.status_code == 200
    assert listed.json()["total"] == 0
    assert missing.status_code == 404


def test_health_remains_public_without_csrf(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
