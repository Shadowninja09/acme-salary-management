from argon2 import PasswordHasher
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings
from app.services.auth import verify_hr_manager_credentials

_TEST_USERNAME = "hr.manager"
_TEST_PASSWORD = "test-only-correct-password"
_TEST_PASSWORD_HASH = PasswordHasher().hash(_TEST_PASSWORD)
_PLACEHOLDER_DATABASE_URL = "postgresql+psycopg://pytest:pytest@127.0.0.1:1/acme_unused"


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


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": _PLACEHOLDER_DATABASE_URL,
        "hr_manager_identity": "audit-hr-manager",
        "hr_manager_username": _TEST_USERNAME,
        "hr_manager_password_hash": _TEST_PASSWORD_HASH,
        "session_cookie_secure": False,
        "csrf_signing_secret": "test-only-csrf-signing-secret-value",
        "csrf_trusted_origins": ["https://hr.test"],
    }
    values.update(overrides)
    return _IsolatedSettings(**values)


def test_correct_username_and_password_are_accepted() -> None:
    assert (
        verify_hr_manager_credentials(_TEST_USERNAME, _TEST_PASSWORD, _settings())
        is True
    )


def test_incorrect_username_is_rejected() -> None:
    assert (
        verify_hr_manager_credentials("other.user", _TEST_PASSWORD, _settings())
        is False
    )


def test_incorrect_password_is_rejected() -> None:
    assert (
        verify_hr_manager_credentials(
            _TEST_USERNAME,
            "test-only-wrong-password",
            _settings(),
        )
        is False
    )


def test_username_comparison_is_exact() -> None:
    assert (
        verify_hr_manager_credentials("HR.manager", _TEST_PASSWORD, _settings())
        is False
    )


def test_missing_username_configuration_is_rejected() -> None:
    try:
        _IsolatedSettings(
            database_url=_PLACEHOLDER_DATABASE_URL,
            hr_manager_identity="audit-hr-manager",
            hr_manager_password_hash=_TEST_PASSWORD_HASH,
            session_cookie_secure=False,
            csrf_signing_secret="test-only-csrf-signing-secret-value",
            csrf_trusted_origins=["https://hr.test"],
        )
    except ValidationError as exc:
        assert "hr_manager_username" in str(exc)
    else:
        raise AssertionError("expected Settings validation to fail")


def test_blank_password_hash_configuration_is_rejected() -> None:
    try:
        _settings(hr_manager_password_hash="")
    except ValidationError as exc:
        assert "hr_manager_password_hash" in str(exc)
    else:
        raise AssertionError("expected Settings validation to fail")


def test_valid_generated_argon2_hash_is_accepted() -> None:
    settings = _settings()
    assert (
        settings.hr_manager_password_hash.get_secret_value() == _TEST_PASSWORD_HASH
    )


def test_example_placeholder_password_hash_is_rejected() -> None:
    placeholder = "replace_with_a_generated_argon2_hash"
    try:
        _settings(hr_manager_password_hash=placeholder)
    except ValidationError as exc:
        _assert_invalid_hash_config_error(exc, placeholder)
    else:
        raise AssertionError("expected Settings validation to fail")


def test_malformed_password_hash_configuration_is_rejected() -> None:
    malformed = "not-an-argon2-hash"
    try:
        _settings(hr_manager_password_hash=malformed)
    except ValidationError as exc:
        _assert_invalid_hash_config_error(exc, malformed)
    else:
        raise AssertionError("expected Settings validation to fail")


def _assert_invalid_hash_config_error(exc: ValidationError, secret: str) -> None:
    message = str(exc)
    assert "hr_manager_password_hash" in message
    assert "valid Argon2 encoded hash" in message
    assert secret not in message
    for error in exc.errors(include_input=False):
        assert secret not in str(error)


def test_settings_store_password_hash_not_plaintext() -> None:
    settings = _settings()
    assert "hr_manager_password" not in Settings.model_fields
    assert isinstance(settings.hr_manager_password_hash, SecretStr)
    assert settings.hr_manager_password_hash.get_secret_value() == _TEST_PASSWORD_HASH
    assert _TEST_PASSWORD not in repr(settings)
    assert _TEST_PASSWORD not in str(settings.hr_manager_password_hash)
    assert settings.hr_manager_identity == "audit-hr-manager"
    assert settings.hr_manager_username == _TEST_USERNAME
    assert settings.hr_manager_identity != settings.hr_manager_username
