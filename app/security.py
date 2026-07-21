"""Primitivas de autenticação sem segredos ou senhas no código-fonte."""

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
COOKIE_NAME = "brcom_session"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return "$".join(
        (
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def is_password_hash(value: str) -> bool:
    return value.startswith(f"{PASSWORD_ALGORITHM}$")


def verify_password(password: str, stored_hash: str) -> bool:
    if not is_password_hash(stored_hash):
        return False
    try:
        _, iterations, salt_encoded, digest_encoded = stored_hash.split("$", 3)
        salt = base64.urlsafe_b64decode(salt_encoded.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_encoded.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _session_secret() -> str:
    secret = os.getenv("SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("SESSION_SECRET deve ter pelo menos 32 caracteres")
    return secret


def validate_security_config() -> None:
    _session_secret()


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    hours = int(os.getenv("SESSION_HOURS", "8"))
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=hours)},
        _session_secret(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, _session_secret(), algorithms=["HS256"])
    return int(payload["sub"])


def cookie_is_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
