from functools import lru_cache
from urllib.parse import urlsplit

from argon2 import extract_parameters
from argon2.exceptions import InvalidHashError
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    hr_manager_identity: str
    hr_manager_username: str = Field(min_length=1)
    hr_manager_password_hash: SecretStr = Field(min_length=1)
    session_cookie_secure: bool
    session_max_age_seconds: int = Field(default=28800, ge=1)
    csrf_signing_secret: SecretStr
    csrf_trusted_origins: list[str] = Field(min_length=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("hr_manager_password_hash")
    @classmethod
    def hr_manager_password_hash_must_be_encoded_argon2(
        cls, value: SecretStr
    ) -> SecretStr:
        try:
            extract_parameters(value.get_secret_value())
        except InvalidHashError:
            raise ValueError(
                "HR_MANAGER_PASSWORD_HASH must be a valid Argon2 encoded hash"
            ) from None
        return value

    @field_validator("csrf_signing_secret")
    @classmethod
    def csrf_signing_secret_must_be_configured(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret.strip()) < 32 or secret != secret.strip():
            raise ValueError(
                "CSRF_SIGNING_SECRET must be at least 32 characters without "
                "leading or trailing whitespace"
            )
        return value

    @field_validator("csrf_trusted_origins")
    @classmethod
    def csrf_trusted_origins_must_be_exact_origins(
        cls, value: list[str]
    ) -> list[str]:
        from app.services.csrf import canonicalize_origin

        stored: list[str] = []
        seen: set[str] = set()
        for origin in value:
            canonical = canonicalize_origin(origin, allow_path=False)
            if canonical is None:
                raise ValueError(
                    "CSRF_TRUSTED_ORIGINS entries must be exact origins "
                    "(scheme://host[:port]) with a valid hostname and "
                    "canonical port, and with no path, query, or wildcard"
                )
            parsed = urlsplit(origin)
            stored_origin = f"{parsed.scheme}://{parsed.netloc}"
            if canonical not in seen:
                seen.add(canonical)
                stored.append(stored_origin)
        if not stored:
            raise ValueError("CSRF_TRUSTED_ORIGINS must include at least one origin")
        return stored


@lru_cache
def get_settings() -> Settings:
    return Settings()
