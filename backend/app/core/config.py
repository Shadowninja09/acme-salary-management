from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
