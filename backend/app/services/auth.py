import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

_password_hasher = PasswordHasher()


def verify_hr_manager_credentials(
    username: str,
    password: str,
    settings: Settings,
) -> bool:
    """Return True when username and password match the configured HR Manager."""
    username_matches = _usernames_match(username, settings.hr_manager_username)
    password_matches = _password_matches(
        password,
        settings.hr_manager_password_hash.get_secret_value(),
    )
    return username_matches and password_matches


def _usernames_match(supplied_username: str, configured_username: str) -> bool:
    return hmac.compare_digest(
        supplied_username.encode("utf-8"),
        configured_username.encode("utf-8"),
    )


def _password_matches(supplied_password: str, configured_password_hash: str) -> bool:
    try:
        return _password_hasher.verify(configured_password_hash, supplied_password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False
